"""Request correlation and centralized error-handling tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from pymongo.errors import (
    ExecutionTimeout,
    NetworkTimeout,
    OperationFailure,
    ServerSelectionTimeoutError,
)

from app.api.deps import get_item_repository
from app.core.errors import RETRY_AFTER_SECONDS
from app.main import app


def test_request_id_is_echoed_when_supplied() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "trace-42"})
    assert response.headers["X-Request-ID"] == "trace-42"


def test_request_id_is_generated_when_absent() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.headers.get("X-Request-ID")


def test_unhandled_error_returns_generic_envelope_without_leaking_internals() -> None:
    class ExplodingRepository:
        async def list(self, limit: int, skip: int) -> list[dict[str, Any]]:
            raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_item_repository] = ExplodingRepository
    try:
        # Server exceptions are converted to responses rather than re-raised so
        # the centralized handler can be asserted.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/items")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text


@pytest.mark.parametrize(
    "error",
    [
        ServerSelectionTimeoutError("no primary at mongo-0.internal:27017"),
        NetworkTimeout("mongo-0.internal:27017: timed out"),
        ExecutionTimeout("operation exceeded time limit", 50),
    ],
    ids=["unreachable", "network-timeout", "deadline-expired"],
)
def test_an_unavailable_database_answers_503_with_retry_after(error: Exception) -> None:
    class UnavailableRepository:
        async def create(self, data: Any) -> dict[str, Any]:
            raise error

    path = "/api/v1/items"
    before = (
        REGISTRY.get_sample_value(
            "http_requests_total", {"method": "POST", "path": path, "status": "503"}
        )
        or 0.0
    )
    app.dependency_overrides[get_item_repository] = UnavailableRepository
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(path, json={"name": "spool", "quantity": 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.headers["Retry-After"] == str(RETRY_AFTER_SECONDS)
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "mongo-0" not in response.text
    # The failure is counted where the availability objective reads it.
    after = REGISTRY.get_sample_value(
        "http_requests_total", {"method": "POST", "path": path, "status": "503"}
    )
    assert after == before + 1


def test_other_database_errors_remain_internal_errors() -> None:
    class BrokenRepository:
        async def create(self, data: Any) -> dict[str, Any]:
            raise OperationFailure("document failed validation", 121)

    app.dependency_overrides[get_item_repository] = BrokenRepository
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/api/v1/items", json={"name": "spool", "quantity": 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
