"""Dead-letter capture, counting, and replay against an in-memory JetStream."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.api import RawStreamMsg, StreamState
from nats.js.errors import BadRequestError, NotFoundError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from prometheus_client import REGISTRY
from pymongo.errors import ServerSelectionTimeoutError

from app import replay as replay_command
from app.deadletter import (
    DEAD_LETTER_STREAM,
    DeadLetterReplayer,
    ReplayReport,
    dead_letter_stream_config,
    ensure_dead_letter_stream,
    refresh_dead_letter_count,
)
from app.models import ItemEvent
from tests.conftest import item_event

_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
_TRACEPARENT = f"00-{_TRACE_ID}-b7ad6b7169203331-01"


def _advisory(stream_seq: int, *, terminated: bool = False, deliveries: int = 5) -> bytes:
    """An advisory as the server renders it, with fields this service ignores."""
    kind = "terminated" if terminated else "max_deliver"
    return json.dumps(
        {
            "type": f"io.nats.jetstream.advisory.v1.{kind}",
            "id": "Q3l0ZHZpc29yeQ",
            "timestamp": "2026-10-29T12:00:00.000000000Z",
            "stream": "ITEMS",
            "consumer": "audit-service",
            "stream_seq": stream_seq,
            "deliveries": deliveries,
            "domain": "",
        }
    ).encode()


class FakeJetStream:
    """The stream reads and deletes the replayer performs, held in memory."""

    def __init__(self) -> None:
        self.streams: dict[str, dict[int, RawStreamMsg]] = {"ITEMS": {}, DEAD_LETTER_STREAM: {}}

    def put(
        self, stream: str, seq: int, data: bytes, headers: dict[str, str] | None = None
    ) -> None:
        subject = "items.created" if stream == "ITEMS" else "$JS.EVENT.ADVISORY"
        self.streams[stream][seq] = RawStreamMsg(
            subject=subject, seq=seq, data=data, headers=headers
        )

    async def stream_info(self, name: str) -> MagicMock:
        sequences = sorted(self.streams[name])
        state = StreamState(
            messages=len(sequences),
            bytes=0,
            first_seq=sequences[0] if sequences else 0,
            last_seq=sequences[-1] if sequences else 0,
            consumer_count=0,
        )
        return MagicMock(state=state)

    async def get_msg(self, stream_name: str, seq: int) -> RawStreamMsg:
        try:
            return self.streams[stream_name][seq]
        except KeyError:
            raise NotFoundError from None

    async def delete_msg(self, stream_name: str, seq: int) -> bool:
        del self.streams[stream_name][seq]
        return True


def _replayer(js: FakeJetStream, record: AsyncMock) -> DeadLetterReplayer:
    repository = MagicMock()
    repository.record = record
    return DeadLetterReplayer(js, repository, "ITEMS")  # type: ignore[arg-type]


def _event_bytes(**overrides: Any) -> bytes:
    return json.dumps(item_event(**overrides)).encode()


def test_the_stream_captures_only_this_consumers_advisories() -> None:
    config = dead_letter_stream_config("ITEMS", "audit-service")

    assert config.name == DEAD_LETTER_STREAM
    assert config.subjects == [
        "$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.ITEMS.audit-service",
        "$JS.EVENT.ADVISORY.CONSUMER.MSG_TERMINATED.ITEMS.audit-service",
    ]
    # Matches the item stream, which holds the events the dead letters point to.
    assert config.max_age == 7 * 24 * 60 * 60


async def test_an_existing_stream_is_updated_to_the_declared_configuration() -> None:
    js = MagicMock()
    js.add_stream = AsyncMock(side_effect=BadRequestError())
    js.update_stream = AsyncMock()

    await ensure_dead_letter_stream(js, "ITEMS", "audit-service")

    js.update_stream.assert_awaited_once_with(dead_letter_stream_config("ITEMS", "audit-service"))


async def test_the_count_follows_the_stream_and_survives_an_unreachable_broker() -> None:
    js = FakeJetStream()
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4))
    js.put(DEAD_LETTER_STREAM, 2, _advisory(9))
    await refresh_dead_letter_count(js)  # type: ignore[arg-type]
    assert REGISTRY.get_sample_value("audit_dead_letters") == 2.0

    unreachable = MagicMock()
    unreachable.stream_info = AsyncMock(side_effect=NatsTimeoutError)
    await refresh_dead_letter_count(unreachable)

    # The last known count stands rather than reading as resolved.
    assert REGISTRY.get_sample_value("audit_dead_letters") == 2.0


async def test_an_abandoned_event_is_recorded_and_its_dead_letter_removed() -> None:
    js = FakeJetStream()
    js.put("ITEMS", 4, _event_bytes())
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4, deliveries=5))
    record = AsyncMock(return_value=True)

    report = await _replayer(js, record).replay(dry_run=False, discard_unrecoverable=False)

    assert record.await_args is not None
    event, attempt = record.await_args.args
    assert isinstance(event, ItemEvent)
    assert event.id == item_event()["id"]
    assert attempt == 6
    assert report.outcomes == {"recorded": 1}
    assert report.remaining == 0
    assert js.streams[DEAD_LETTER_STREAM] == {}
    # The item stream remains an exact record of what was published.
    assert 4 in js.streams["ITEMS"]


async def test_an_event_already_recorded_resolves_as_a_duplicate() -> None:
    js = FakeJetStream()
    js.put("ITEMS", 4, _event_bytes())
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4))

    report = await _replayer(js, AsyncMock(return_value=False)).replay(
        dry_run=False, discard_unrecoverable=False
    )

    assert report.outcomes == {"duplicate": 1}
    assert js.streams[DEAD_LETTER_STREAM] == {}


async def test_a_dry_run_reports_without_recording_or_removing() -> None:
    js = FakeJetStream()
    js.put("ITEMS", 4, _event_bytes())
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4))
    record = AsyncMock()

    report = await _replayer(js, record).replay(dry_run=True, discard_unrecoverable=True)

    record.assert_not_awaited()
    assert report.outcomes == {"replayable": 1}
    assert report.remaining == 1
    assert 1 in js.streams[DEAD_LETTER_STREAM]


@pytest.mark.parametrize("discard", [False, True], ids=["kept", "discarded"])
async def test_unrecoverable_dead_letters_are_kept_unless_discarded(discard: bool) -> None:
    js = FakeJetStream()
    # A terminated malformed event, and an advisory whose event has aged out.
    js.put("ITEMS", 4, _event_bytes(type="order.created"))
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4, terminated=True, deliveries=1))
    js.put(DEAD_LETTER_STREAM, 2, _advisory(3))
    record = AsyncMock()

    report = await _replayer(js, record).replay(dry_run=False, discard_unrecoverable=discard)

    record.assert_not_awaited()
    assert report.outcomes == {"malformed": 1, "expired": 1}
    assert report.remaining == (0 if discard else 2)
    assert sorted(js.streams[DEAD_LETTER_STREAM]) == ([] if discard else [1, 2])


async def test_a_storage_failure_stops_the_replay_and_keeps_the_dead_letter() -> None:
    js = FakeJetStream()
    js.put("ITEMS", 4, _event_bytes())
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4))
    record = AsyncMock(side_effect=ServerSelectionTimeoutError("down"))

    with pytest.raises(ServerSelectionTimeoutError):
        await _replayer(js, record).replay(dry_run=False, discard_unrecoverable=True)

    assert 1 in js.streams[DEAD_LETTER_STREAM]


async def test_sequences_resolved_earlier_are_skipped() -> None:
    js = FakeJetStream()
    js.put("ITEMS", 4, _event_bytes())
    js.put("ITEMS", 5, _event_bytes(id="4f3c2b1a-0000-4000-8000-000000000002"))
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4))
    js.put(DEAD_LETTER_STREAM, 3, _advisory(5))

    report = await _replayer(js, AsyncMock(return_value=True)).replay(
        dry_run=False, discard_unrecoverable=False
    )

    assert report.outcomes == {"recorded": 2}
    assert js.streams[DEAD_LETTER_STREAM] == {}


async def test_an_empty_stream_needs_no_reads() -> None:
    report = await _replayer(FakeJetStream(), AsyncMock()).replay(
        dry_run=False, discard_unrecoverable=False
    )

    assert report == ReplayReport()


async def test_the_replay_continues_the_events_original_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("app.deadletter.tracer", provider.get_tracer("test"))
    js = FakeJetStream()
    js.put("ITEMS", 4, _event_bytes(), headers={"traceparent": _TRACEPARENT})
    js.put(DEAD_LETTER_STREAM, 1, _advisory(4))

    await _replayer(js, AsyncMock(return_value=True)).replay(
        dry_run=False, discard_unrecoverable=False
    )

    (span,) = exporter.get_finished_spans()
    assert span.name == "replay items.created"
    assert span.kind is SpanKind.CONSUMER
    assert f"{span.context.trace_id:032x}" == _TRACE_ID
    assert span.parent is not None
    assert f"{span.parent.span_id:016x}" == "b7ad6b7169203331"


@pytest.mark.parametrize(("remaining", "exit_code"), [(0, 0), (2, 1)])
def test_the_command_summarizes_and_fails_while_dead_letters_remain(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    remaining: int,
    exit_code: int,
) -> None:
    report = ReplayReport(remaining=remaining)
    report.outcomes["recorded"] = 3
    seen: list[Any] = []

    async def run(args: Any) -> ReplayReport:
        seen.append(args)
        return report

    monkeypatch.setattr(replay_command, "_run", run)

    assert replay_command.main(["--discard-unrecoverable"]) == exit_code
    assert seen[0].discard_unrecoverable is True
    assert seen[0].dry_run is False
    summary = json.loads(capsys.readouterr().out)
    assert summary == {"outcomes": {"recorded": 3}, "remaining": remaining}
