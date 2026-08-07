"""Pytest fixtures providing hermetic, database-free application wiring."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Environment is configured before the application is imported so that settings
# validation succeeds and startup performs no network I/O.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "test")
os.environ.setdefault("MONGODB_PING_ON_STARTUP", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_item_repository, get_mongodb  # noqa: E402
from app.main import app  # noqa: E402
from tests.fakes import FakeItemRepository, FakeMongoDB  # noqa: E402


@pytest.fixture
def fake_repository() -> FakeItemRepository:
    return FakeItemRepository()


@pytest.fixture
def client(fake_repository: FakeItemRepository) -> Iterator[TestClient]:
    # The persistence and connectivity dependencies are replaced with in-memory
    # doubles so that endpoint behavior is verified in isolation from MongoDB.
    app.dependency_overrides[get_item_repository] = lambda: fake_repository
    app.dependency_overrides[get_mongodb] = lambda: FakeMongoDB(healthy=True)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
