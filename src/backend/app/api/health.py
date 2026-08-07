"""Liveness and readiness endpoints for orchestrator health probing.

Liveness reflects process health only and never depends on external systems, so
that a transient database outage does not trigger pod restarts. Readiness gates
traffic on downstream connectivity and returns 503 while dependencies are down.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app import __version__
from app.api.deps import get_mongodb
from app.db.mongodb import MongoDB

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive", "version": __version__}


@router.get("/health/ready")
async def readiness(
    response: Response,
    mongodb: MongoDB = Depends(get_mongodb),
) -> dict[str, object]:
    database_up = await mongodb.ping()
    if not database_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": {"mongodb": "down"}}
    return {"status": "ready", "checks": {"mongodb": "up"}}
