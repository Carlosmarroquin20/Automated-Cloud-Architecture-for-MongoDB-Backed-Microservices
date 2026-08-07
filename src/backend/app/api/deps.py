"""Shared FastAPI dependencies for request-scoped resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fastapi import Depends, Request

from app.db.mongodb import MongoDB
from app.repositories.item_repository import ItemRepository

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase


def get_mongodb(request: Request) -> MongoDB:
    # The connection manager is created once during application startup and stored
    # on application state for reuse across requests.
    return cast(MongoDB, request.app.state.mongodb)


def get_database(mongodb: MongoDB = Depends(get_mongodb)) -> AsyncDatabase[dict[str, Any]]:
    return mongodb.database


def get_item_repository(
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> ItemRepository:
    return ItemRepository(database)
