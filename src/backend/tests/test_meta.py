"""Service metadata endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_root_returns_service_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["version"]
    assert "environment" in body
