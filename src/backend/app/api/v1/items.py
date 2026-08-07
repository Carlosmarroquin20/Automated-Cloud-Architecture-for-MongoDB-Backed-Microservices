"""Item resource endpoints (API v1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_item_repository
from app.core.exceptions import EntityNotFoundError
from app.models.item import ItemCreate, ItemResponse, ItemUpdate
from app.repositories.item_repository import ItemRepository

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict[str, Any]:
    return await repository.create(payload)


@router.get("", response_model=list[ItemResponse])
async def list_items(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    repository: ItemRepository = Depends(get_item_repository),
) -> list[dict[str, Any]]:
    return await repository.list(limit=limit, skip=skip)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: str,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict[str, Any]:
    item = await repository.get(item_id)
    if item is None:
        raise EntityNotFoundError(f"item '{item_id}' was not found")
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: str,
    payload: ItemUpdate,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict[str, Any]:
    item = await repository.update(item_id, payload)
    if item is None:
        raise EntityNotFoundError(f"item '{item_id}' was not found")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str,
    repository: ItemRepository = Depends(get_item_repository),
) -> Response:
    deleted = await repository.delete(item_id)
    if not deleted:
        raise EntityNotFoundError(f"item '{item_id}' was not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
