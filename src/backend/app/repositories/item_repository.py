"""Persistence operations for the item resource.

The repository isolates MongoDB access behind an explicit interface so that the
transport layer remains storage-agnostic and unit tests can substitute an
in-memory implementation without a live database.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.core.exceptions import InvalidObjectIdError
from app.models.item import ItemCreate, ItemUpdate

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase

COLLECTION_NAME = "items"


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
        self._collection: AsyncCollection[dict[str, Any]] = database[COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        # Descending traversal of the creation timestamp backs the default
        # reverse-chronological listing without a full collection scan.
        await self._collection.create_index("created_at")

    async def create(self, data: ItemCreate) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document = data.model_dump()
        document["created_at"] = now
        document["updated_at"] = now
        result = await self._collection.insert_one(document)
        document["_id"] = result.inserted_id
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
        document = await self._collection.find_one_and_update(
            {"_id": object_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
        return _serialize(document) if document else None

    async def delete(self, item_id: str) -> bool:
        result = await self._collection.delete_one({"_id": _to_object_id(item_id)})
        return result.deleted_count == 1
