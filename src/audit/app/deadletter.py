"""Dead letters: events this consumer gave up on, held until they are resolved.

JetStream publishes an advisory whenever a message exhausts its delivery
attempts or is terminated. A dedicated stream captures the advisories for this
consumer, so the broker itself records every abandoned event, whatever the
cause: storage errors, repeated crashes, or processing that outlasted the
acknowledgement wait. Code on the failure path is the least reliable place to
record a failure, so the consumer does not attempt it.

An advisory carries the event's position in the item stream, not the event, so
a replay reads the event back from that stream. Both streams keep messages for
seven days, which bounds the window for resolving a dead letter; the alert on
unresolved dead letters fires as soon as one exists.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from nats.errors import Error as NatsError
from nats.js import JetStreamContext
from nats.js.api import RawStreamMsg, RetentionPolicy, StorageType, StreamConfig
from nats.js.errors import BadRequestError, NotFoundError
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind
from prometheus_client import Gauge
from pydantic import BaseModel, ConfigDict, ValidationError

from app.models import ItemEvent
from app.repository import AuditRepository

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

DEAD_LETTER_STREAM = "AUDIT_DEAD_LETTERS"

_ADVISORY_PREFIX = "$JS.EVENT.ADVISORY.CONSUMER"
_RETENTION_SECONDS = 7 * 24 * 60 * 60
_EXHAUSTED_ADVISORY_TYPE = "io.nats.jetstream.advisory.v1.max_deliver"

DEAD_LETTERS = Gauge(
    "audit_dead_letters",
    "Events abandoned by the consumer and not yet replayed or discarded.",
)

Outcome = Literal["recorded", "duplicate", "replayable", "malformed", "expired"]
# A recorded or duplicate event is in the history, so its dead letter is done.
_RESOLVED: frozenset[Outcome] = frozenset({"recorded", "duplicate"})
# Replaying these again would fail identically; only discarding resolves them.
_UNRECOVERABLE: frozenset[Outcome] = frozenset({"malformed", "expired"})


def dead_letter_stream_config(source_stream: str, durable_name: str) -> StreamConfig:
    return StreamConfig(
        name=DEAD_LETTER_STREAM,
        # Scoped to one consumer of one stream: other consumers' failures are
        # theirs to handle, and each consumer replays into its own store.
        subjects=[
            f"{_ADVISORY_PREFIX}.MAX_DELIVERIES.{source_stream}.{durable_name}",
            f"{_ADVISORY_PREFIX}.MSG_TERMINATED.{source_stream}.{durable_name}",
        ],
        storage=StorageType.FILE,
        retention=RetentionPolicy.LIMITS,
        # Matches the item stream: past that age the event a dead letter points
        # to no longer exists, so keeping the dead letter longer serves nothing.
        max_age=_RETENTION_SECONDS,
        num_replicas=1,
    )


async def ensure_dead_letter_stream(
    js: JetStreamContext, source_stream: str, durable_name: str
) -> None:
    """Declare the dead-letter stream, updating an existing one to match."""
    config = dead_letter_stream_config(source_stream, durable_name)
    try:
        await js.add_stream(config)
    except BadRequestError:
        await js.update_stream(config)


async def refresh_dead_letter_count(js: JetStreamContext) -> None:
    """Publish the number of unresolved dead letters; skipped while unreachable."""
    try:
        info = await js.stream_info(DEAD_LETTER_STREAM)
    except NatsError as exc:
        logger.debug("dead-letter count unavailable", extra={"error": str(exc)})
        return
    DEAD_LETTERS.set(info.state.messages)


class Advisory(BaseModel):
    """The fields of a JetStream delivery advisory this service relies on."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str
    stream_seq: int
    deliveries: int
    timestamp: datetime
    reason: str | None = None

    @property
    def cause(self) -> str:
        return "exhausted" if self.type == _EXHAUSTED_ADVISORY_TYPE else "terminated"


@dataclass
class ReplayReport:
    outcomes: Counter[str] = field(default_factory=Counter)
    remaining: int = 0


class DeadLetterReplayer:
    """Resolves dead letters by recording their events directly in the history.

    Replaying into the store rather than republishing to the item stream keeps
    the stream an exact record of what the producer published, and leaves other
    consumers of that stream unaffected. Recording is idempotent, so a replay
    that races the live consumer, or runs twice, records each event once.
    """

    def __init__(
        self, js: JetStreamContext, repository: AuditRepository, source_stream: str
    ) -> None:
        self._js = js
        self._repository = repository
        self._source_stream = source_stream

    async def replay(self, *, dry_run: bool, discard_unrecoverable: bool) -> ReplayReport:
        report = ReplayReport()
        state = (await self._js.stream_info(DEAD_LETTER_STREAM)).state
        if state.messages == 0:
            return report
        for sequence in range(state.first_seq, state.last_seq + 1):
            try:
                letter = await self._js.get_msg(DEAD_LETTER_STREAM, sequence)
            except NotFoundError:
                # Resolved by an earlier replay.
                continue
            outcome = await self._resolve(letter, dry_run=dry_run)
            report.outcomes[outcome] += 1
            settled = outcome in _RESOLVED or (discard_unrecoverable and outcome in _UNRECOVERABLE)
            if settled and not dry_run:
                await self._js.delete_msg(DEAD_LETTER_STREAM, sequence)
            else:
                report.remaining += 1
        return report

    async def _resolve(self, letter: RawStreamMsg, *, dry_run: bool) -> Outcome:
        try:
            advisory = Advisory.model_validate_json(letter.data or b"")
        except ValidationError:
            logger.error("unreadable dead letter", extra={"dead_letter_seq": letter.seq})
            return "malformed"
        context = {
            "dead_letter_seq": letter.seq,
            "stream_seq": advisory.stream_seq,
            "cause": advisory.cause,
            "deliveries": advisory.deliveries,
        }
        try:
            source = await self._js.get_msg(self._source_stream, advisory.stream_seq)
        except NotFoundError:
            logger.error("dead letter outlived its event", extra=context)
            return "expired"
        try:
            event = ItemEvent.model_validate_json(source.data or b"")
        except ValidationError:
            logger.error("dead letter holds a malformed event", extra=context)
            return "malformed"
        context["event_id"] = event.id
        if dry_run:
            logger.info("dead letter is replayable", extra=context)
            return "replayable"

        # The replay continues the event's original trace, so the trace shows
        # the request, the publish, the abandoned deliveries, and the recovery.
        with tracer.start_as_current_span(
            f"replay {source.subject}",
            context=extract(source.headers or {}),
            kind=SpanKind.CONSUMER,
            attributes={
                "messaging.system": "nats",
                "messaging.destination.name": source.subject or "",
                "messaging.message.id": event.id,
            },
        ):
            recorded = await self._repository.record(event, advisory.deliveries + 1)
        outcome: Outcome = "recorded" if recorded else "duplicate"
        logger.info("dead letter replayed", extra={**context, "outcome": outcome})
        return outcome
