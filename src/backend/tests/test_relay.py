"""Outbox relay tests.

The outbox collection and the broker are replaced with doubles so that ordering,
failure handling, deduplication, and trace propagation are verified without
MongoDB or NATS.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from prometheus_client import REGISTRY

from app.messaging.relay import OutboxRelay, PublishError, encode_event
from app.messaging.stream import STREAM_CONFIG, subject_for

_NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


def _event(event_id: str, event_type: str = "item.created", **extra: Any) -> dict[str, Any]:
    return {
        "_id": event_id,
        "specversion": "1.0",
        "type": event_type,
        "source": "/services/items-api",
        "subject": "6720f0c2a1b2c3d4e5f60718",
        "time": _NOW,
        "datacontenttype": "application/json",
        "data": {"item": {"id": "6720f0c2a1b2c3d4e5f60718", "created_at": _NOW}},
        "traceparent": None,
        "published_at": None,
        **extra,
    }


class _Publisher:
    """Records publishes; fails on configured event ids; flags duplicates."""

    def __init__(self, fail_on: set[str] | None = None, duplicates: set[str] | None = None):
        self.sent: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self._fail_on = fail_on or set()
        self._duplicates = duplicates or set()

    async def publish(self, subject: str, payload: bytes, headers: dict[str, str]) -> bool:
        event_id = headers["Nats-Msg-Id"]
        if event_id in self._fail_on:
            raise PublishError("no responders")
        self.sent.append((subject, json.loads(payload), headers))
        return event_id in self._duplicates


def _outbox(events: list[dict[str, Any]], oldest: dict[str, Any] | None = None) -> MagicMock:
    outbox = MagicMock()
    outbox.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=events
    )
    outbox.update_one = AsyncMock()
    outbox.find_one = AsyncMock(return_value=oldest)
    return outbox


def _relay(outbox: MagicMock, publisher: _Publisher, batch_size: int = 100) -> OutboxRelay:
    return OutboxRelay(outbox, publisher, batch_size=batch_size, poll_interval=0.01)


def _metric(name: str, labels: dict[str, str] | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def test_encoding_is_a_structured_cloudevent() -> None:
    subject, payload, headers = encode_event(_event("e-1", traceparent=_TRACEPARENT))
    message = json.loads(payload)

    assert subject == "items.created"
    assert message["id"] == "e-1"
    assert message["type"] == "item.created"
    assert message["time"] == _NOW.isoformat()
    assert message["data"]["item"]["created_at"] == _NOW.isoformat()
    # Storage bookkeeping never leaks into the published contract.
    assert not {"_id", "published_at", "traceparent"} & message.keys()
    assert headers == {
        "Nats-Msg-Id": "e-1",
        "Content-Type": "application/cloudevents+json",
    }


def test_every_event_type_maps_to_a_subject_in_the_stream() -> None:
    for event_type in ("item.created", "item.updated", "item.deleted"):
        assert subject_for(event_type).startswith("items.")
    with pytest.raises(ValueError, match="no subject"):
        subject_for("order.created")
    assert STREAM_CONFIG.subjects == ["items.>"]
    assert STREAM_CONFIG.duplicate_window == 120


async def test_pending_events_are_published_in_order_and_recorded() -> None:
    outbox = _outbox([_event("e-1"), _event("e-2", "item.deleted")])
    publisher = _Publisher()
    before = _metric("outbox_events_published_total", {"type": "item.deleted"})

    published = await _relay(outbox, publisher).publish_pending()

    assert published == 2
    assert [subject for subject, _, _ in publisher.sent] == ["items.created", "items.deleted"]
    outbox.find.assert_called_once_with({"published_at": None})
    recorded = [call.args for call in outbox.update_one.await_args_list]
    assert [filter_["_id"] for filter_, _ in recorded] == ["e-1", "e-2"]
    # Recording is conditional on the event still being pending.
    assert all(filter_["published_at"] is None for filter_, _ in recorded)
    assert all(update["$set"]["published_at"].tzinfo for _, update in recorded)
    assert _metric("outbox_events_published_total", {"type": "item.deleted"}) == before + 1


async def test_a_failed_publish_stops_the_batch_to_preserve_order() -> None:
    outbox = _outbox([_event("e-1"), _event("e-2"), _event("e-3")])
    publisher = _Publisher(fail_on={"e-2"})
    failures = _metric("outbox_publish_failures_total")

    published = await _relay(outbox, publisher).publish_pending()

    assert published == 1
    assert [headers["Nats-Msg-Id"] for _, _, headers in publisher.sent] == ["e-1"]
    assert outbox.update_one.await_count == 1
    assert _metric("outbox_publish_failures_total") == failures + 1


async def test_broker_duplicates_are_recorded_as_published_and_counted() -> None:
    outbox = _outbox([_event("e-1")])
    duplicates = _metric("outbox_publish_duplicates_total")

    await _relay(outbox, _Publisher(duplicates={"e-1"})).publish_pending()

    assert outbox.update_one.await_count == 1
    assert _metric("outbox_publish_duplicates_total") == duplicates + 1


async def test_the_stored_trace_context_travels_in_the_message_headers() -> None:
    outbox = _outbox([_event("e-1", traceparent=_TRACEPARENT), _event("e-2")])
    publisher = _Publisher()

    await _relay(outbox, publisher).publish_pending()

    # Tracing is not enabled in tests, so the stored context is forwarded as is;
    # an event recorded outside any trace carries no header at all.
    first, second = (headers for _, _, headers in publisher.sent)
    assert first["traceparent"] == _TRACEPARENT
    assert "traceparent" not in second


async def test_backlog_age_reflects_the_oldest_pending_event() -> None:
    outbox = _outbox([], oldest=_event("e-9", time=datetime.now(timezone.utc) - timedelta(30)))

    await _relay(outbox, _Publisher()).publish_pending()

    assert _metric("outbox_oldest_pending_age_seconds") >= 30 * 24 * 60 * 60


async def test_a_drained_outbox_reports_no_backlog() -> None:
    await _relay(_outbox([]), _Publisher()).publish_pending()

    assert _metric("outbox_oldest_pending_age_seconds") == 0.0


async def test_run_beats_and_stops_when_requested(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    relay = OutboxRelay(
        _outbox([]), _Publisher(), batch_size=10, poll_interval=60.0, heartbeat_path=heartbeat
    )
    stop = asyncio.Event()
    # The stop request arrives while the relay idles in its 60-second poll wait.
    asyncio.get_running_loop().call_later(0.05, stop.set)

    # The idle wait ends on the stop request instead of running to the timeout.
    await asyncio.wait_for(relay.run(stop), timeout=1.0)
    assert heartbeat.exists()
