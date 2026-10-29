"""Persistence operations for the item resource.

The repository isolates MongoDB access behind an explicit interface so that the
transport layer remains storage-agnostic and unit tests can substitute an
in-memory implementation without a live database.

Every mutation commits together with its domain event in a single transaction
(see ``app.repositories.outbox``), which requires a replica set; Atlas clusters
are replica sets, and local deployments run a single-node one.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TypeVar

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.core.exceptions import InvalidObjectIdError
from app.models.item import ItemCreate, ItemUpdate
from app.repositories.outbox import (
    OUTBOX_COLLECTION,
    EventType,
    build_event,
    ensure_outbox_indexes,
)

if TYPE_CHECKING:
    from pymongo.asynchronous.client_session import AsyncClientSession
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase

COLLECTION_NAME = "items"

_T = TypeVar("_T")


def _to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise InvalidObjectIdError(f"'{value}' is not a valid identifier") from exc


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    # Project the persistence identifier to a client-facing string field and drop
    # the native ObjectId to keep the API contract free of storage details.
    document["id"] = str(document.pop("_id"))
    return document


def _snapshot(document: dict[str, Any]) -> dict[str, Any]:
    # Events carry the full item state so consumers need no callback to this
    # service; the copy keeps serialization from mutating the stored document.
    return {"item": _serialize(dict(document))}


def _build_filter(tag: str | None, query: str | None) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    if tag:
        conditions["tags"] = tag
    if query:
        # Case-insensitive substring match. The input is escaped so it is treated
        # as a literal value rather than an attacker-controlled expression.
        conditions["name"] = {"$regex": re.escape(query), "$options": "i"}
    return conditions


class ItemRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._database = database
        self._collection: AsyncCollection[dict[str, Any]] = database[COLLECTION_NAME]
        self._outbox: AsyncCollection[dict[str, Any]] = database[OUTBOX_COLLECTION]

    async def ensure_indexes(self) -> None:
        # Descending traversal of the creation timestamp backs the default
        # reverse-chronological listing without a full collection scan.
        await self._collection.create_index("created_at")
        await ensure_outbox_indexes(self._database)

    async def _transact(self, operation: Callable[[AsyncClientSession], Awaitable[_T]]) -> _T:
        # with_transaction retries the whole operation on transient errors and the
        # commit on an unknown commit result, as the driver recommends; the
        # operation must therefore be safe to run more than once.
        async with self._database.client.start_session() as session:
            return await session.with_transaction(operation)

    async def create(self, data: ItemCreate) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document = data.model_dump()
        document["created_at"] = now
        document["updated_at"] = now

        async def write(session: AsyncClientSession) -> None:
            result = await self._collection.insert_one(document, session=session)
            document["_id"] = result.inserted_id
            event = build_event(
                EventType.ITEM_CREATED, str(result.inserted_id), _snapshot(document)
            )
            await self._outbox.insert_one(event, session=session)

        await self._transact(write)
        return _serialize(document)

    async def list(
        self,
        limit: int,
        skip: int,
        tag: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        cursor = (
            self._collection.find(_build_filter(tag, query))
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [_serialize(document) async for document in cursor]

    async def count(self, tag: str | None = None, query: str | None = None) -> int:
        return await self._collection.count_documents(_build_filter(tag, query))

    async def get(self, item_id: str) -> dict[str, Any] | None:
        document = await self._collection.find_one({"_id": _to_object_id(item_id)})
        return _serialize(document) if document else None

    async def update(self, item_id: str, data: ItemUpdate) -> dict[str, Any] | None:
        object_id = _to_object_id(item_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            document = await self._collection.find_one({"_id": object_id})
            return _serialize(document) if document else None

        changes["updated_at"] = datetime.now(timezone.utc)

        async def write(session: AsyncClientSession) -> dict[str, Any] | None:
            document = await self._collection.find_one_and_update(
                {"_id": object_id},
                {"$set": changes},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            # A missing item changes nothing, so no event is recorded.
            if document is not None:
                data = {**_snapshot(document), "changed_fields": sorted(changes)}
                event = build_event(EventType.ITEM_UPDATED, item_id, data)
                await self._outbox.insert_one(event, session=session)
            return document

        document = await self._transact(write)
        return _serialize(document) if document else None

    async def delete(self, item_id: str) -> bool:
        object_id = _to_object_id(item_id)

        async def write(session: AsyncClientSession) -> bool:
            # The removed document is returned so the event records the final
            # state of the item, which an audit trail needs after deletion.
            document = await self._collection.find_one_and_delete(
                {"_id": object_id}, session=session
            )
            if document is None:
                return False
            event = build_event(EventType.ITEM_DELETED, item_id, _snapshot(document))
            await self._outbox.insert_one(event, session=session)
            return True

        return await self._transact(write)
