"""Message settlement tests: acknowledgement, deduplication, rejection, retry."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats.errors import TimeoutError as NatsTimeoutError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from prometheus_client import REGISTRY
from pymongo.errors import ServerSelectionTimeoutError

from app.config import Settings
from app.consumer import AuditConsumer, EventHandler, redelivery_delay
from app.models import ItemEvent
from tests.conftest import item_event

_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
_TRACEPARENT = f"00-{_TRACE_ID}-b7ad6b7169203331-01"


def _message(
    payload: dict[str, Any] | bytes, attempt: int = 1, headers: dict[str, str] | None = None
) -> MagicMock:
    msg = MagicMock()
    msg.subject = "items.created"
    msg.data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    msg.headers = headers
    msg.metadata.num_delivered = attempt
    msg.ack, msg.nak, msg.term = AsyncMock(), AsyncMock(), AsyncMock()
    return msg


def _handler(record: AsyncMock) -> EventHandler:
    repository = MagicMock()
    repository.record = record
    return EventHandler(repository, max_deliver=5)


def _consumed(outcome: str) -> float:
    return REGISTRY.get_sample_value("audit_events_consumed_total", {"outcome": outcome}) or 0.0


async def test_a_new_event_is_recorded_then_acknowledged() -> None:
    record = AsyncMock(return_value=True)
    msg = _message(item_event(), attempt=2)
    before = _consumed("recorded")

    await _handler(record).handle(msg)

    assert record.await_args is not None
    event, attempt = record.await_args.args
    assert isinstance(event, ItemEvent)
    assert event.subject == item_event()["subject"]
    assert attempt == 2
    msg.ack.assert_awaited_once()
    msg.nak.assert_not_awaited()
    assert _consumed("recorded") == before + 1


async def test_a_redelivered_duplicate_is_acknowledged_without_recording_twice() -> None:
    before = _consumed("duplicate")
    msg = _message(item_event())

    await _handler(AsyncMock(return_value=False)).handle(msg)

    msg.ack.assert_awaited_once()
    assert _consumed("duplicate") == before + 1


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        item_event(type="order.created"),
        item_event(specversion="0.3"),
        {key: value for key, value in item_event().items() if key != "subject"},
    ],
    ids=["unparseable", "unknown-type", "unsupported-spec", "missing-subject"],
)
async def test_a_malformed_event_is_terminated_and_never_retried(
    payload: dict[str, Any] | bytes,
) -> None:
    record = AsyncMock()
    msg = _message(payload)

    await _handler(record).handle(msg)

    msg.term.assert_awaited_once()
    msg.ack.assert_not_awaited()
    msg.nak.assert_not_awaited()
    record.assert_not_awaited()


async def test_a_storage_failure_requests_a_delayed_redelivery() -> None:
    msg = _message(item_event(), attempt=3)

    await _handler(AsyncMock(side_effect=ServerSelectionTimeoutError("down"))).handle(msg)

    msg.nak.assert_awaited_once_with(delay=redelivery_delay(3))
    msg.ack.assert_not_awaited()


def test_redelivery_delay_doubles_and_is_capped() -> None:
    assert [redelivery_delay(attempt) for attempt in (1, 2, 3, 4)] == [1.0, 2.0, 4.0, 8.0]
    assert redelivery_delay(20) == 30.0


async def test_processing_continues_the_trace_carried_by_the_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("app.consumer.tracer", provider.get_tracer("test"))

    msg = _message(item_event(), headers={"traceparent": _TRACEPARENT})
    await _handler(AsyncMock(return_value=True)).handle(msg)

    (span,) = exporter.get_finished_spans()
    assert span.kind is SpanKind.CONSUMER
    assert f"{span.context.trace_id:032x}" == _TRACE_ID
    assert span.parent is not None
    assert f"{span.parent.span_id:016x}" == "b7ad6b7169203331"


async def test_binding_state_follows_the_broker_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    # While the client reconnects, fetches only time out, exactly as on an idle
    # stream; the reported state must come from the connection events instead.
    stop = asyncio.Event()
    callbacks: dict[str, Any] = {}
    observed: list[bool] = []
    repository = MagicMock()
    repository.ensure_indexes = AsyncMock()
    consumer = AuditConsumer(Settings(), repository)

    async def fetch(*_: Any, **__: Any) -> list[Any]:
        observed.append(consumer.connected)
        await callbacks["disconnected_cb"]()
        observed.append(consumer.connected)
        await callbacks["reconnected_cb"]()
        observed.append(consumer.connected)
        stop.set()
        raise NatsTimeoutError

    async def connect(**kwargs: Any) -> MagicMock:
        callbacks.update(kwargs)
        client = MagicMock(is_closed=False)
        client.drain = AsyncMock()
        subscription = MagicMock()
        subscription.fetch = fetch
        js = client.jetstream.return_value
        js.add_stream = AsyncMock()
        js.stream_info = AsyncMock(return_value=MagicMock(state=MagicMock(messages=0)))
        js.pull_subscribe = AsyncMock(return_value=subscription)
        return client

    monkeypatch.setattr("app.consumer.nats.connect", connect)

    await asyncio.wait_for(consumer.run(stop), timeout=1.0)

    assert observed == [True, False, True]
    assert REGISTRY.get_sample_value("audit_consumer_connected") == 0.0


async def test_the_dead_letter_stream_exists_before_the_consumer_binds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An advisory published before its stream exists is lost, so the order is
    # part of the guarantee that no abandoned event goes unrecorded.
    stop = asyncio.Event()
    calls: list[str] = []
    repository = MagicMock()
    repository.ensure_indexes = AsyncMock()

    async def fetch(*_: Any, **__: Any) -> list[Any]:
        stop.set()
        raise NatsTimeoutError

    subscription = MagicMock()
    subscription.fetch = fetch

    async def add_stream(config: Any) -> None:
        calls.append(f"add {config.name}")

    async def stream_info(name: str) -> MagicMock:
        calls.append(f"count {name}")
        return MagicMock(state=MagicMock(messages=3))

    async def pull_subscribe(*_: Any, **kwargs: Any) -> MagicMock:
        calls.append(f"bind {kwargs['durable']}")
        return subscription

    async def connect(**_: Any) -> MagicMock:
        client = MagicMock(is_closed=False)
        client.drain = AsyncMock()
        js = client.jetstream.return_value
        js.add_stream, js.stream_info, js.pull_subscribe = add_stream, stream_info, pull_subscribe
        return client

    monkeypatch.setattr("app.consumer.nats.connect", connect)

    await asyncio.wait_for(AuditConsumer(Settings(), repository).run(stop), timeout=1.0)

    assert calls == [
        "add AUDIT_DEAD_LETTERS",
        "bind audit-service",
        "count AUDIT_DEAD_LETTERS",
    ]
    assert REGISTRY.get_sample_value("audit_dead_letters") == 3.0
