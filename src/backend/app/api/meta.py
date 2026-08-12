"""Service metadata endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.core.config import Settings, get_settings

router = APIRouter(tags=["meta"])


@router.get("/", summary="Service metadata")
async def root(settings: Settings = Depends(get_settings)) -> dict[str, str | None]:
    return {
        "name": settings.app_name,
        "version": __version__,
        "environment": settings.app_env,
        "docs": None if settings.is_production else "/docs",
    }
