"""Outbox relay: publishes committed outbox events to NATS JetStream.

The relay reads pending events oldest first, publishes each one, and records the
publication time. A crash between publishing and recording republishes the event
on the next pass, so delivery is at-least-once. Two layers absorb the resulting
duplicates: JetStream drops a repeated ``Nats-Msg-Id`` inside its duplicate
window, and consumers deduplicate by event id beyond it.

A batch stops at the first failed publish, so later events never overtake an
earlier one for the same item. The relay runs as a single replica; a second
instance would stay correct, because of the deduplication above, but would only
publish the same events twice.

Run with ``python -m app.messaging.relay``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from nats.errors import Error as NatsError
from opentelemetry import trace
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import SpanKind
from prometheus_client import Counter, Gauge, start_http_server
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.tracing import configure_worker_tracing
from app.db.mongodb import MongoDB
from app.messaging.stream import STREAM_NAME, connect, ensure_stream, subject_for
from app.repositories.outbox import OUTBOX_COLLECTION

if TYPE_CHECKING:
    from nats.js import JetStreamContext
    from pymongo.asynchronous.collection import AsyncCollection

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

SERVICE_NAME = "outbox-relay"

# The liveness probe checks that this file is touched every pass, which detects
# a relay that is running but stuck without exposing an HTTP endpoint for it.
HEARTBEAT_PATH = Path("/tmp/outbox-relay.heartbeat")  # noqa: S108

_PUBLISH_TIMEOUT_SECONDS = 5.0
_PENDING = {"published_at": None}

EVENTS_PUBLISHED = Counter(
    "outbox_events_published_total",
    "Outbox events published to JetStream.",
    ["type"],
)
DUPLICATES_DROPPED = Counter(
    "outbox_publish_duplicates_total",
    "Publishes that JetStream acknowledged as duplicates of an earlier message.",
)
PUBLISH_FAILURES = Counter(
    "outbox_publish_failures_total",
    "Publish attempts that failed and will be retried.",
)
OLDEST_PENDING_AGE = Gauge(
    "outbox_oldest_pending_age_seconds",
    "Age of the oldest unpublished event; zero when the outbox is drained.",
)


class PublishError(Exception):
    """Raised when the broker does not acknowledge a publish."""


class Publisher(Protocol):
    async def publish(self, subject: str, payload: bytes, headers: dict[str, str]) -> bool:
        """Publish a message and report whether the broker saw it as a duplicate."""


class JetStreamPublisher:
    def __init__(self, jetstream: JetStreamContext) -> None:
        self._jetstream = jetstream

    async def publish(self, subject: str, payload: bytes, headers: dict[str, str]) -> bool:
        try:
            ack = await self._jetstream.publish(
                subject,
                payload,
                timeout=_PUBLISH_TIMEOUT_SECONDS,
                stream=STREAM_NAME,
                headers=headers,
            )
        except NatsError as exc:
            raise PublishError(str(exc)) from exc
        return bool(ack.duplicate)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def encode_event(event: dict[str, Any]) -> tuple[str, bytes, dict[str, str]]:
    """Render an outbox document as a structured-mode CloudEvent message."""
    message = {
        "id": event["_id"],
        "specversion": event["specversion"],
        "type": event["type"],
        "source": event["source"],
        "subject": event["subject"],
        "time": event["time"],
        "datacontenttype": event["datacontenttype"],
        "data": event["data"],
    }
    payload = json.dumps(message, default=_json_default, separators=(",", ":")).encode()
    headers = {
        # The event id doubles as the broker's deduplication key.
        "Nats-Msg-Id": event["_id"],
        "Content-Type": "application/cloudevents+json",
    }
    return subject_for(event["type"]), payload, headers


class OutboxRelay:
    def __init__(
        self,
        outbox: AsyncCollection[dict[str, Any]],
        publisher: Publisher,
        *,
        batch_size: int,
        poll_interval: float,
        heartbeat_path: Path | None = None,
    ) -> None:
        self._outbox = outbox
        self._publisher = publisher
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._heartbeat_path = heartbeat_path

    async def publish_pending(self) -> int:
        """Publish one batch of pending events, oldest first; return how many."""
        cursor = self._outbox.find(_PENDING).sort("time", ASCENDING).limit(self._batch_size)
        # Polling reads repeat every interval and have no causal link to any
        # request, so they are kept out of traces; the publish of each event and
        # its bookkeeping write remain traced.
        with suppress_instrumentation():
            pending = await cursor.to_list()
        published = 0
        for event in pending:
            try:
                duplicate = await self._publish(event)
            except PublishError as exc:
                PUBLISH_FAILURES.inc()
                logger.warning(
                    "outbox publish failed; the batch resumes on the next pass",
                    extra={"event_id": event["_id"], "error": str(exc)},
                )
                break
            # The pending condition makes the update a no-op if another pass
            # already recorded this event.
            await self._outbox.update_one(
                {"_id": event["_id"], **_PENDING},
                {"$set": {"published_at": datetime.now(timezone.utc)}},
            )
            EVENTS_PUBLISHED.labels(type=event["type"]).inc()
            if duplicate:
                DUPLICATES_DROPPED.inc()
            published += 1
        await self._record_backlog()
        return published

    async def _publish(self, event: dict[str, Any]) -> bool:
        subject, payload, headers = encode_event(event)
        stored = event.get("traceparent")
        # The publish span continues the trace of the request that wrote the
        # event, and its own context is forwarded so consumers become children
        # of the publish rather than of the original request.
        parent = extract({"traceparent": stored}) if stored else None
        with tracer.start_as_current_span(
            f"publish {subject}",
            context=parent,
            kind=SpanKind.PRODUCER,
            attributes={
                "messaging.system": "nats",
                "messaging.destination.name": subject,
                "messaging.message.id": event["_id"],
            },
        ):
            carrier: dict[str, str] = {}
            inject(carrier)
            # With tracing disabled no span context exists, so the stored
            # context is forwarded unchanged to keep the chain intact.
            traceparent = carrier.get("traceparent") or stored
            if traceparent:
                headers["traceparent"] = traceparent
            return await self._publisher.publish(subject, payload, headers)

    async def _record_backlog(self) -> None:
        with suppress_instrumentation():
            oldest = await self._outbox.find_one(_PENDING, sort=[("time", ASCENDING)])
        age = 0.0
        if oldest is not None:
            age = max(0.0, (datetime.now(timezone.utc) - oldest["time"]).total_seconds())
        OLDEST_PENDING_AGE.set(age)

    def _beat(self) -> None:
        if self._heartbeat_path is not None:
            self._heartbeat_path.touch()

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            published = 0
            try:
                published = await self.publish_pending()
            except PyMongoError as exc:
                logger.warning("outbox read failed; retrying", extra={"error": str(exc)})
            self._beat()
            # A full batch suggests a backlog, so the next pass starts at once;
            # otherwise the relay idles until the next poll or a stop request.
            if published < self._batch_size:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self._poll_interval)


async def serve(settings: Settings) -> None:
    configure_logging(settings.log_level)
    configure_worker_tracing(settings, SERVICE_NAME)
    start_http_server(settings.outbox_relay_metrics_port)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    mongodb = MongoDB(settings)
    await mongodb.connect()
    client = await connect(settings.nats_url, SERVICE_NAME)
    try:
        jetstream = client.jetstream()
        await ensure_stream(jetstream)
        relay = OutboxRelay(
            mongodb.database[OUTBOX_COLLECTION],
            JetStreamPublisher(jetstream),
            batch_size=settings.outbox_relay_batch_size,
            poll_interval=settings.outbox_relay_poll_interval_seconds,
            heartbeat_path=HEARTBEAT_PATH,
        )
        logger.info("outbox relay started", extra={"stream": STREAM_NAME})
        started = time.monotonic()
        await relay.run(stop)
        logger.info(
            "outbox relay stopping",
            extra={"uptime_seconds": round(time.monotonic() - started, 1)},
        )
    finally:
        # Draining flushes in-flight publishes before the connection closes.
        await client.drain()
        await mongodb.disconnect()


def main() -> None:
    asyncio.run(serve(get_settings()))


if __name__ == "__main__":
    main()
