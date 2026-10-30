"""Durable JetStream consumer that records item events.

Every message is acknowledged explicitly and only after its outcome is settled,
so a crash before the acknowledgement makes JetStream redeliver it:

- recorded or already recorded (a duplicate): ``ack``;
- malformed and therefore never processable: ``term``, so it is not redelivered;
- storage unavailable: ``nak`` with a delay that grows per delivery attempt.

JetStream stops redelivering after ``max_deliver`` attempts, which bounds the
work a persistently failing event can cause; the abandoned event becomes a dead
letter (``app.deadletter``) instead of disappearing. The consumer is durable, so
its position survives restarts, and replicas pulling from it share the load.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import nats
from nats.errors import Error as NatsError
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind
from prometheus_client import Counter, Gauge
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from app.backoff import backoff_delays
from app.config import Settings
from app.deadletter import ensure_dead_letter_stream, refresh_dead_letter_count
from app.models import ItemEvent
from app.repository import AuditRepository

if TYPE_CHECKING:
    from nats.aio.client import Client
    from nats.aio.msg import Msg

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

STREAM_NAME = "ITEMS"
FILTER_SUBJECT = "items.>"

_FETCH_TIMEOUT_SECONDS = 5.0
_RECONNECT_BASE_DELAY_SECONDS = 0.5
_REDELIVERY_DELAY_CAP_SECONDS = 30.0
_DEAD_LETTER_REFRESH_SECONDS = 15.0

EVENTS_CONSUMED = Counter(
    "audit_events_consumed_total",
    "Consumed item events by outcome.",
    ["outcome"],
)
CONSUMER_CONNECTED = Gauge(
    "audit_consumer_connected",
    "Whether the consumer is bound to the stream (1) or reconnecting (0).",
)


def redelivery_delay(attempt: int) -> float:
    """Delay before the next delivery: doubling per attempt, capped."""
    return float(min(2 ** (attempt - 1), _REDELIVERY_DELAY_CAP_SECONDS))


class EventHandler:
    def __init__(self, repository: AuditRepository, max_deliver: int) -> None:
        self._repository = repository
        self._max_deliver = max_deliver

    async def handle(self, msg: Msg) -> None:
        attempt = msg.metadata.num_delivered
        # The span continues the trace carried in the message headers, which
        # links this processing to the publish and the originating request.
        with tracer.start_as_current_span(
            f"process {msg.subject}",
            context=extract(msg.headers or {}),
            kind=SpanKind.CONSUMER,
            attributes={
                "messaging.system": "nats",
                "messaging.destination.name": msg.subject,
                "messaging.message.delivery_attempt": attempt,
            },
        ):
            await self._settle(msg, attempt)

    async def _settle(self, msg: Msg, attempt: int) -> None:
        try:
            event = ItemEvent.model_validate_json(msg.data)
        except ValidationError as exc:
            # A malformed message fails identically on every delivery, so it is
            # terminated instead of being retried.
            EVENTS_CONSUMED.labels(outcome="rejected").inc()
            logger.error(
                "rejected malformed event",
                extra={"subject": msg.subject, "errors": exc.error_count()},
            )
            await msg.term()
            return

        try:
            recorded = await self._repository.record(event, attempt)
        except PyMongoError as exc:
            EVENTS_CONSUMED.labels(outcome="retried").inc()
            final = attempt >= self._max_deliver
            logger.log(
                logging.ERROR if final else logging.WARNING,
                "event not recorded; "
                + ("attempts exhausted; dead-lettered" if final else "redelivery requested"),
                extra={"event_id": event.id, "attempt": attempt, "error": str(exc)},
            )
            await msg.nak(delay=redelivery_delay(attempt))
            return

        await msg.ack()
        EVENTS_CONSUMED.labels(outcome="recorded" if recorded else "duplicate").inc()


class AuditConsumer:
    def __init__(self, settings: Settings, repository: AuditRepository) -> None:
        self._settings = settings
        self._repository = repository
        self._handler = EventHandler(repository, settings.consumer_max_deliver)
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def _set_connected(self, connected: bool) -> None:
        self._connected = connected
        CONSUMER_CONNECTED.set(1 if connected else 0)

    async def _on_disconnected(self) -> None:
        self._set_connected(False)
        logger.warning("consumer lost the broker connection; reconnecting")

    async def _on_reconnected(self) -> None:
        self._set_connected(True)
        logger.info("consumer reconnected to the broker")

    def _config(self) -> ConsumerConfig:
        return ConsumerConfig(
            durable_name=self._settings.consumer_durable_name,
            filter_subject=FILTER_SUBJECT,
            deliver_policy=DeliverPolicy.ALL,
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=self._settings.consumer_ack_wait_seconds,
            max_deliver=self._settings.consumer_max_deliver,
        )

    async def run(self, stop: asyncio.Event) -> None:
        """Consume until stopped, reconnecting with jittered backoff on failure.

        The stream is declared by the outbox relay, so binding fails until the
        relay has started; that case is retried like any other outage, which
        keeps the services free of startup ordering constraints.
        """
        delays = backoff_delays(_RECONNECT_BASE_DELAY_SECONDS)
        while not stop.is_set():
            client: Client | None = None
            try:
                await self._repository.ensure_indexes()
                client = await nats.connect(
                    servers=[self._settings.nats_url],
                    name=self._settings.app_name,
                    connect_timeout=5,
                    allow_reconnect=True,
                    max_reconnect_attempts=-1,
                    reconnect_time_wait=2,
                    # The client reconnects by itself and raises nothing while it
                    # does: fetches only time out, which is indistinguishable from
                    # an idle stream. The binding state therefore follows the
                    # client's connection events rather than fetch outcomes.
                    disconnected_cb=self._on_disconnected,
                    reconnected_cb=self._on_reconnected,
                )
                js = client.jetstream()
                # Declared before binding, so the advisory for an event abandoned
                # on its first deliveries already has a stream to land in.
                await ensure_dead_letter_stream(
                    js, STREAM_NAME, self._settings.consumer_durable_name
                )
                subscription = await js.pull_subscribe(
                    FILTER_SUBJECT,
                    durable=self._settings.consumer_durable_name,
                    stream=STREAM_NAME,
                    config=self._config(),
                )
                self._set_connected(True)
                logger.info("consumer bound to stream", extra={"stream": STREAM_NAME})
                delays = backoff_delays(_RECONNECT_BASE_DELAY_SECONDS)
                loop = asyncio.get_running_loop()
                next_refresh = loop.time()
                while not stop.is_set():
                    if loop.time() >= next_refresh:
                        await refresh_dead_letter_count(js)
                        next_refresh = loop.time() + _DEAD_LETTER_REFRESH_SECONDS
                    try:
                        messages = await subscription.fetch(
                            self._settings.consumer_batch_size, timeout=_FETCH_TIMEOUT_SECONDS
                        )
                    except NatsTimeoutError:
                        continue
                    for msg in messages:
                        await self._handler.handle(msg)
            except (NatsError, OSError, PyMongoError) as exc:
                self._set_connected(False)
                delay = next(delays)
                logger.warning(
                    "consumer unavailable; retrying",
                    extra={"retry_in_seconds": round(delay, 3), "error": str(exc)},
                )
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=delay)
            finally:
                if client is not None and not client.is_closed:
                    # Draining lets in-flight acknowledgements reach the server.
                    with contextlib.suppress(NatsError):
                        await client.drain()
        self._set_connected(False)
