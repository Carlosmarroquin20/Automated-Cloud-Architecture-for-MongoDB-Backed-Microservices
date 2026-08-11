"""Resilience tests for the MongoDB connection manager.

The native client is replaced with a mock so that retry, backoff, and readiness
semantics are verified deterministically without a live database.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.db.mongodb import MongoDB

_REQUIRED = {"mongodb_uri": "mongodb://localhost:27017", "mongodb_db_name": "example"}


def _settings(**overrides: Any) -> Settings:
    # A zero base delay keeps backoff instantaneous under test. The startup probe
    # is enabled explicitly because the shared test environment disables it.
    params: dict[str, Any] = {
        **_REQUIRED,
        "mongodb_connect_retry_base_delay_seconds": 0.0,
        "mongodb_ping_on_startup": True,
    }
    params.update(overrides)
    return Settings(**params)


def _patch_client(monkeypatch: pytest.MonkeyPatch, command: AsyncMock) -> None:
    client = MagicMock()
    client.admin.command = command
    monkeypatch.setattr("app.db.mongodb.AsyncMongoClient", lambda *args, **kwargs: client)


async def test_ping_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    command = AsyncMock(
        side_effect=[ServerSelectionTimeoutError("x"), ServerSelectionTimeoutError("x"), {"ok": 1}]
    )
    _patch_client(monkeypatch, command)

    mongo = MongoDB(_settings(mongodb_connect_max_retries=5))
    await mongo.connect()

    assert mongo.is_connected is True
    assert command.await_count == 3


async def test_ping_exhausts_retries_and_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    command = AsyncMock(side_effect=ServerSelectionTimeoutError("down"))
    _patch_client(monkeypatch, command)

    mongo = MongoDB(_settings(mongodb_connect_max_retries=2))
    await mongo.connect()

    # Startup proceeds without a live connection; readiness gating handles it.
    assert mongo.is_connected is False
    assert command.await_count == 3


async def test_startup_probe_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    command = AsyncMock()
    _patch_client(monkeypatch, command)

    mongo = MongoDB(_settings(mongodb_ping_on_startup=False))
    await mongo.connect()

    assert mongo.is_connected is False
    command.assert_not_awaited()


async def test_ping_reports_false_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    command = AsyncMock(side_effect=ServerSelectionTimeoutError("down"))
    _patch_client(monkeypatch, command)

    mongo = MongoDB(_settings(mongodb_ping_on_startup=False))
    await mongo.connect()

    assert await mongo.ping() is False


def test_database_property_requires_connection() -> None:
    mongo = MongoDB(_settings())
    with pytest.raises(RuntimeError):
        _ = mongo.database
