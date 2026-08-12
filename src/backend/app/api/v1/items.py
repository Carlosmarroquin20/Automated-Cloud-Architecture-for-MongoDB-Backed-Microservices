"""Item resource endpoints (API v1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_item_repository
from app.core.exceptions import EntityNotFoundError
from app.models.errors import ErrorResponse
from app.models.item import ItemCreate, ItemResponse, ItemUpdate
from app.repositories.item_repository import ItemRepository

router = APIRouter(prefix="/items", tags=["items"])

# Documented error responses reuse the uniform error envelope so the schema
# advertises the exact shape clients receive on failure.
_ID_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid identifier"},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Item not found"},
}


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    responses={422: {"model": ErrorResponse, "description": "Validation error"}},
)
async def create_item(
    payload: ItemCreate,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict[str, Any]:
    return await repository.create(payload)


@router.get(
    "",
    response_model=list[ItemResponse],
    summary="List items",
    responses={
        200: {
            "headers": {
                "X-Total-Count": {
                    "description": "Total number of items matching the filter.",
                    "schema": {"type": "integer"},
                }
            }
        }
    },
)
async def list_items(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum items to return."),
    skip: int = Query(default=0, ge=0, description="Number of items to skip."),
    tag: str | None = Query(default=None, description="Filter by an exact tag."),
    q: str | None = Query(default=None, description="Case-insensitive name search."),
    repository: ItemRepository = Depends(get_item_repository),
) -> list[dict[str, Any]]:
    items = await repository.list(limit=limit, skip=skip, tag=tag, query=q)
    # The total matching count is published as a header so pagination metadata is
    # available without changing the array response contract.
    response.headers["X-Total-Count"] = str(await repository.count(tag=tag, query=q))
    return items


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Retrieve an item",
    responses=_ID_RESPONSES,
)
async def get_item(
    item_id: str,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict[str, Any]:
    item = await repository.get(item_id)
    if item is None:
        raise EntityNotFoundError(f"item '{item_id}' was not found")
    return item


@router.patch(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update an item",
    responses=_ID_RESPONSES,
)
async def update_item(
    item_id: str,
    payload: ItemUpdate,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict[str, Any]:
    item = await repository.update(item_id, payload)
    if item is None:
        raise EntityNotFoundError(f"item '{item_id}' was not found")
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
    responses=_ID_RESPONSES,
)
async def delete_item(
    item_id: str,
    repository: ItemRepository = Depends(get_item_repository),
) -> Response:
    deleted = await repository.delete(item_id)
    if not deleted:
        raise EntityNotFoundError(f"item '{item_id}' was not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
