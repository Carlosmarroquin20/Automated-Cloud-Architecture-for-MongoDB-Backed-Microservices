"""HTTP surface: the item history endpoint, health probes, and metrics."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.consumer import AuditConsumer
from app.models import AuditEntry
from app.repository import AuditRepository

router = APIRouter(prefix="/audit", tags=["audit"])
health_router = APIRouter(tags=["health"])

# Item identifiers are MongoDB ObjectIds rendered as 24 hexadecimal characters.
_ITEM_ID = Path(pattern=r"^[0-9a-f]{24}$", description="Item identifier.")


def get_repository(request: Request) -> AuditRepository:
    return cast(AuditRepository, request.app.state.repository)


def get_mongo_client(request: Request) -> AsyncMongoClient[dict[str, Any]]:
    return cast(AsyncMongoClient[dict[str, Any]], request.app.state.mongo_client)


def get_consumer_state(request: Request) -> str:
    consumer = cast("AuditConsumer | None", getattr(request.app.state, "consumer", None))
    if consumer is None:
        return "disabled"
    return "connected" if consumer.connected else "disconnected"


@router.get(
    "/items/{item_id}/events",
    response_model=list[AuditEntry],
    summary="List the recorded events of an item",
)
async def item_history(
    item_id: str = _ITEM_ID,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum events to return."),
    repository: AuditRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    # Events are returned oldest first, so the list reads as the item's history.
    return await repository.history(item_id, limit)


@health_router.get("/health/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@health_router.get("/health/ready", summary="Readiness probe")
async def ready(
    client: AsyncMongoClient[dict[str, Any]] = Depends(get_mongo_client),
    consumer: str = Depends(get_consumer_state),
) -> JSONResponse:
    # Readiness depends only on the database the API reads. The consumer's state
    # is reported but does not gate traffic: history stays readable while the
    # broker is unavailable, and consumption resumes on its own.
    try:
        await client.admin.command("ping")
    except PyMongoError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "checks": {"mongodb": "down", "consumer": consumer}},
        )
    return JSONResponse(
        content={"status": "ready", "checks": {"mongodb": "up", "consumer": consumer}}
    )


@health_router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
