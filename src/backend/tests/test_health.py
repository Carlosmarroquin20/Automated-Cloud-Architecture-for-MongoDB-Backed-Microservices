"""Health probe endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_mongodb
from app.main import app
from tests.fakes import FakeMongoDB


def test_liveness_is_always_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_ok_when_database_reachable() -> None:
    app.dependency_overrides[get_mongodb] = lambda: FakeMongoDB(healthy=True)
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["checks"]["mongodb"] == "up"


def test_readiness_unavailable_when_database_unreachable() -> None:
    app.dependency_overrides[get_mongodb] = lambda: FakeMongoDB(healthy=False)
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["checks"]["mongodb"] == "down"
