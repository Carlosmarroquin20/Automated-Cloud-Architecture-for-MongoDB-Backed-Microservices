"""Audit history persistence.

Idempotency rests on the event id serving as the document ``_id``: a redelivered
event collides with the unique primary key and is reported as a duplicate rather
than recorded twice. No read-before-write is needed, so two replicas handling
the same event concurrently cannot both record it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.models import ItemEvent

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase

EVENTS_COLLECTION = "events"


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    document["id"] = document.pop("_id")
    return document


class AuditRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._events: AsyncCollection[dict[str, Any]] = database[EVENTS_COLLECTION]

    async def ensure_indexes(self) -> None:
        # Serves the per-item history query in chronological order.
        await self._events.create_index(
            [("subject", ASCENDING), ("time", ASCENDING)], name="history_by_item"
        )

    async def record(self, event: ItemEvent, delivery_attempt: int) -> bool:
        """Record an event; return False when it was already recorded."""
        document = {
            "_id": event.id,
            "type": event.type,
            "source": event.source,
            "subject": event.subject,
            "time": event.time,
            "data": event.data,
            "received_at": datetime.now(timezone.utc),
            "delivery_attempt": delivery_attempt,
        }
        try:
            await self._events.insert_one(document)
        except DuplicateKeyError:
            return False
        return True

    async def history(self, item_id: str, limit: int) -> list[dict[str, Any]]:
        cursor = (
            self._events.find({"subject": item_id}, {"delivery_attempt": False})
            .sort("time", ASCENDING)
            .limit(limit)
        )
        return [_serialize(document) async for document in cursor]
