"""In-memory test doubles mirroring the persistence and connectivity contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import InvalidObjectIdError
from app.models.item import ItemCreate, ItemUpdate

_HEX_DIGITS = frozenset("0123456789abcdef")


def _validate_identifier(item_id: str) -> None:
    # Mirrors the ObjectId format validation performed by the MongoDB repository
    # so that identifier-format errors are exercised without a live database.
    if len(item_id) != 24 or any(char not in _HEX_DIGITS for char in item_id.lower()):
        raise InvalidObjectIdError(f"'{item_id}' is not a valid identifier")


class FakeItemRepository:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, data: ItemCreate) -> dict[str, Any]:
        self._counter += 1
        identifier = f"{self._counter:024x}"
        now = datetime.now(timezone.utc)
        document = data.model_dump()
        document.update({"id": identifier, "created_at": now, "updated_at": now})
        self._store[identifier] = document
        return document

    async def list(self, limit: int, skip: int) -> list[dict[str, Any]]:
        ordered = sorted(self._store.values(), key=lambda doc: doc["created_at"], reverse=True)
        return ordered[skip : skip + limit]

    async def get(self, item_id: str) -> dict[str, Any] | None:
        _validate_identifier(item_id)
        return self._store.get(item_id)

    async def update(self, item_id: str, data: ItemUpdate) -> dict[str, Any] | None:
        _validate_identifier(item_id)
        document = self._store.get(item_id)
        if document is None:
            return None
        document.update(data.model_dump(exclude_unset=True))
        document["updated_at"] = datetime.now(timezone.utc)
        return document

    async def delete(self, item_id: str) -> bool:
        _validate_identifier(item_id)
        return self._store.pop(item_id, None) is not None


class FakeMongoDB:
    def __init__(self, *, healthy: bool = True) -> None:
        self._healthy = healthy

    async def ping(self) -> bool:
        return self._healthy
