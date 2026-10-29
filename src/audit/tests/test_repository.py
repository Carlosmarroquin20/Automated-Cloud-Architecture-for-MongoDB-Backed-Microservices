"""Audit repository tests against a collection double."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from pymongo.errors import DuplicateKeyError

from app.models import ItemEvent
from app.repository import EVENTS_COLLECTION, AuditRepository
from tests.conftest import ITEM_ID, item_event


def _repository() -> tuple[AuditRepository, MagicMock]:
    events = MagicMock()
    database = MagicMock()
    database.__getitem__.side_effect = {EVENTS_COLLECTION: events}.__getitem__
    return AuditRepository(database), events


async def test_the_event_id_becomes_the_primary_key() -> None:
    repository, events = _repository()
    events.insert_one = AsyncMock()
    event = ItemEvent.model_validate(item_event())

    assert await repository.record(event, delivery_attempt=1) is True

    document = events.insert_one.await_args.args[0]
    assert document["_id"] == event.id
    assert document["subject"] == ITEM_ID
    assert document["time"] == datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
    assert document["received_at"].tzinfo is not None
    assert document["delivery_attempt"] == 1


async def test_a_repeated_event_id_is_reported_as_a_duplicate() -> None:
    repository, events = _repository()
    events.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000 duplicate key"))

    recorded = await repository.record(ItemEvent.model_validate(item_event()), 2)

    assert recorded is False


async def test_history_is_filtered_by_item_and_ordered_by_time() -> None:
    repository, events = _repository()
    stored = {"_id": "e-1", "type": "item.created", "subject": ITEM_ID}

    async def _cursor() -> object:
        yield dict(stored)

    events.find.return_value.sort.return_value.limit.return_value = _cursor()

    history = await repository.history(ITEM_ID, limit=10)

    assert history == [{"id": "e-1", "type": "item.created", "subject": ITEM_ID}]
    query, projection = events.find.call_args.args
    assert query == {"subject": ITEM_ID}
    assert projection == {"delivery_attempt": False}
    events.find.return_value.sort.assert_called_once_with("time", 1)
    events.find.return_value.sort.return_value.limit.assert_called_once_with(10)


async def test_the_history_index_covers_item_and_time() -> None:
    repository, events = _repository()
    events.create_index = AsyncMock()

    await repository.ensure_indexes()

    keys = events.create_index.await_args.args[0]
    assert keys == [("subject", 1), ("time", 1)]
