"""Transactional outbox tests.

The database, its client, and the session are replaced with doubles so that the
pairing of each state change with its event inside one transaction is verified
without a replica set.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from opentelemetry.sdk.trace import TracerProvider
from pymongo import _csot

from app.models.item import ItemCreate, ItemUpdate
from app.repositories.item_repository import ItemRepository
from app.repositories.outbox import (
    EVENT_SOURCE,
    OUTBOX_COLLECTION,
    PUBLISHED_RETENTION_SECONDS,
    EventType,
    build_event,
)

# W3C Trace Context: version, trace id, parent span id, and a flags byte (sampled
# and, in level 2, random-trace-id bits).
_TRACEPARENT = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")


class _Session:
    """Runs the transaction callback once and counts transactions."""

    def __init__(self) -> None:
        self.transactions = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def with_transaction(self, callback: Callable[[_Session], Awaitable[Any]]) -> Any:
        self.transactions += 1
        return await callback(self)


def _database() -> tuple[MagicMock, MagicMock, MagicMock, _Session]:
    items, outbox, session = MagicMock(), MagicMock(), _Session()
    outbox.insert_one = AsyncMock()
    collections = {"items": items, OUTBOX_COLLECTION: outbox}
    database = MagicMock()
    database.__getitem__.side_effect = collections.__getitem__
    database.client.start_session.return_value = session
    return database, items, outbox, session


def _stored(item_id: ObjectId, **fields: Any) -> dict[str, Any]:
    return {"_id": item_id, "name": "spool", "quantity": 1, "tags": [], **fields}


def test_event_follows_cloudevents_attributes() -> None:
    event = build_event(EventType.ITEM_CREATED, "abc", {"item": {"id": "abc"}})

    uuid.UUID(event["_id"])
    assert event["specversion"] == "1.0"
    assert event["type"] == "item.created"
    assert event["source"] == EVENT_SOURCE
    assert event["subject"] == "abc"
    assert event["time"].tzinfo is not None
    assert event["published_at"] is None
    # No span is active, so there is no trace context to propagate.
    assert event["traceparent"] is None


def test_event_captures_the_active_trace_context() -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("request") as span:
        event = build_event(EventType.ITEM_UPDATED, "abc", {})

    assert _TRACEPARENT.match(event["traceparent"])
    assert f"{span.get_span_context().trace_id:032x}" in event["traceparent"]


async def test_create_commits_item_and_event_in_one_transaction() -> None:
    database, items, outbox, session = _database()
    item_id = ObjectId()
    items.insert_one = AsyncMock(return_value=MagicMock(inserted_id=item_id))

    created = await ItemRepository(database).create(ItemCreate(name="spool", quantity=3))

    assert session.transactions == 1
    assert items.insert_one.await_args.kwargs["session"] is session
    assert outbox.insert_one.await_args.kwargs["session"] is session
    event = outbox.insert_one.await_args.args[0]
    assert event["type"] == "item.created"
    assert event["subject"] == str(item_id)
    assert event["data"]["item"] == created


async def test_update_records_the_new_state_and_changed_fields() -> None:
    database, items, outbox, session = _database()
    item_id = ObjectId()
    items.find_one_and_update = AsyncMock(return_value=_stored(item_id, quantity=7))

    await ItemRepository(database).update(str(item_id), ItemUpdate(quantity=7))

    assert session.transactions == 1
    event = outbox.insert_one.await_args.args[0]
    assert event["type"] == "item.updated"
    assert event["data"]["item"]["quantity"] == 7
    assert event["data"]["changed_fields"] == ["quantity", "updated_at"]


async def test_update_of_a_missing_item_records_no_event() -> None:
    database, items, outbox, _ = _database()
    items.find_one_and_update = AsyncMock(return_value=None)

    result = await ItemRepository(database).update(str(ObjectId()), ItemUpdate(quantity=7))

    assert result is None
    outbox.insert_one.assert_not_awaited()


async def test_delete_records_the_final_state() -> None:
    database, items, outbox, session = _database()
    item_id = ObjectId()
    items.find_one_and_delete = AsyncMock(return_value=_stored(item_id))

    assert await ItemRepository(database).delete(str(item_id)) is True

    assert items.find_one_and_delete.await_args.kwargs["session"] is session
    event = outbox.insert_one.await_args.args[0]
    assert event["type"] == "item.deleted"
    assert event["data"]["item"]["id"] == str(item_id)


async def test_delete_of_a_missing_item_records_no_event() -> None:
    database, items, outbox, _ = _database()
    items.find_one_and_delete = AsyncMock(return_value=None)

    assert await ItemRepository(database).delete(str(ObjectId())) is False
    outbox.insert_one.assert_not_awaited()


async def test_indexes_include_the_pending_scan_and_published_ttl() -> None:
    database, items, outbox, _ = _database()
    items.create_index = AsyncMock()
    outbox.create_index = AsyncMock()

    await ItemRepository(database).ensure_indexes()

    by_name = {call.kwargs["name"]: call for call in outbox.create_index.await_args_list}
    assert set(by_name) == {"pending_by_time", "published_ttl"}
    assert by_name["published_ttl"].kwargs["expireAfterSeconds"] == PUBLISHED_RETENTION_SECONDS


async def test_every_transaction_runs_under_the_configured_deadline() -> None:
    # The driver's own retry budget is 120 seconds; the deadline is what keeps a
    # write during a database outage from outliving the client's request.
    database, items, _, session = _database()
    items.insert_one = AsyncMock()
    deadlines: list[float | None] = []
    run = session.with_transaction

    async def observed(callback: Callable[[_Session], Awaitable[Any]]) -> Any:
        deadlines.append(_csot.get_timeout())
        return await run(callback)

    session.with_transaction = observed  # type: ignore[method-assign]

    await ItemRepository(database, transaction_timeout_seconds=2.5).create(
        ItemCreate(name="spool", quantity=3)
    )

    assert deadlines == [2.5]
    assert _csot.get_timeout() is None
