"""HTTP surface tests with the repository and database client replaced."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app.api import get_mongo_client, get_repository
from app.main import app
from tests.conftest import ITEM_ID

_ENTRY = {
    "id": "e-1",
    "type": "item.created",
    "source": "/services/items-api",
    "subject": ITEM_ID,
    "time": datetime(2026, 10, 28, 12, tzinfo=timezone.utc),
    "data": {"item": {"id": ITEM_ID}},
    "received_at": datetime(2026, 10, 28, 12, 0, 1, tzinfo=timezone.utc),
}


@pytest.fixture
def repository() -> MagicMock:
    repository = MagicMock()
    repository.history = AsyncMock(return_value=[dict(_ENTRY)])
    return repository


@pytest.fixture
def mongo() -> MagicMock:
    client = MagicMock()
    client.admin.command = AsyncMock(return_value={"ok": 1})
    return client


@pytest.fixture
def client(repository: MagicMock, mongo: MagicMock) -> Iterator[TestClient]:
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_mongo_client] = lambda: mongo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_history_lists_the_events_of_an_item(client: TestClient, repository: MagicMock) -> None:
    response = client.get(f"/api/v1/audit/items/{ITEM_ID}/events", params={"limit": 5})

    assert response.status_code == 200
    (entry,) = response.json()
    assert entry["id"] == "e-1"
    assert entry["subject"] == ITEM_ID
    repository.history.assert_awaited_once_with(ITEM_ID, 5)


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/v1/audit/items/not-an-object-id/events", {}),
        (f"/api/v1/audit/items/{ITEM_ID}/events", {"limit": 0}),
        (f"/api/v1/audit/items/{ITEM_ID}/events", {"limit": 501}),
    ],
    ids=["bad-identifier", "limit-too-small", "limit-too-large"],
)
def test_invalid_history_requests_are_rejected(
    client: TestClient, path: str, params: dict[str, Any]
) -> None:
    assert client.get(path, params=params).status_code == 422


def test_readiness_reports_the_database_and_consumer(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    # The consumer is disabled in tests, and readiness does not depend on it.
    assert response.json() == {
        "status": "ready",
        "checks": {"mongodb": "up", "consumer": "disabled"},
    }


def test_readiness_fails_when_the_database_is_unreachable(
    client: TestClient, mongo: MagicMock
) -> None:
    mongo.admin.command = AsyncMock(side_effect=ServerSelectionTimeoutError("down"))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["mongodb"] == "down"


def test_liveness_and_metrics_are_served(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "alive"}
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "audit_events_consumed_total" in metrics.text
