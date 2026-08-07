"""Aggregate router composing API v1 sub-resources."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import items

api_router = APIRouter()
api_router.include_router(items.router)
