"""Request correlation and centralized error-handling tests."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.api.deps import get_item_repository
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
