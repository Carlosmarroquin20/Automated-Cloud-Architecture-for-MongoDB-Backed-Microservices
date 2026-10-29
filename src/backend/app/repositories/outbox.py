"""Transactional outbox for domain events.

Each event is written to the ``outbox`` collection inside the same transaction as
the state change it describes, so a change is never persisted without its event
and an event never describes a change that was rolled back. A separate relay
publishes pending events to the message broker and marks them published.
Delivery is therefore at-least-once, and consumers deduplicate by event id.

Events follow the CloudEvents 1.0 attribute names so their shape is recognizable
to any consumer and maps directly onto broker message headers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from opentelemetry.propagate import inject
from pymongo import ASCENDING

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase

OUTBOX_COLLECTION = "outbox"
EVENT_SOURCE = "/services/items-api"

# Published events are kept for a bounded period for diagnosis and replay, then
# removed by a TTL index. Pending events carry no publication timestamp, which
# the TTL monitor ignores, so an unpublished event is never expired.
PUBLISHED_RETENTION_SECONDS = 7 * 24 * 60 * 60


class EventType(str, Enum):
    ITEM_CREATED = "item.created"
    ITEM_UPDATED = "item.updated"
    ITEM_DELETED = "item.deleted"


def build_event(event_type: EventType, subject: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build an outbox document for a state change on the aggregate ``subject``."""
    # The active trace context, when tracing is enabled, is captured with the
    # event so the relay and the consumers continue the originating trace.
    carrier: dict[str, str] = {}
    inject(carrier)
    return {
        "_id": str(uuid.uuid4()),
        "specversion": "1.0",
        "type": event_type.value,
        "source": EVENT_SOURCE,
        "subject": subject,
        "time": datetime.now(timezone.utc),
        "datacontenttype": "application/json",
        "data": data,
        "traceparent": carrier.get("traceparent"),
        "published_at": None,
    }


async def ensure_outbox_indexes(database: AsyncDatabase[dict[str, Any]]) -> None:
    collection = database[OUTBOX_COLLECTION]
    # The relay reads pending events oldest first; this index serves that scan
    # without touching the published backlog.
    await collection.create_index(
        [("published_at", ASCENDING), ("time", ASCENDING)], name="pending_by_time"
    )
    await collection.create_index(
        "published_at", expireAfterSeconds=PUBLISHED_RETENTION_SECONDS, name="published_ttl"
    )
