"""Hermetic test configuration: no database or broker is contacted."""

from __future__ import annotations

import os
from typing import Any

# Settings are validated when the application is imported, so the environment is
# prepared first. The consumer is disabled so startup never contacts the broker.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("CONSUMER_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")

ITEM_ID = "6720f0c2a1b2c3d4e5f60718"


def item_event(**overrides: Any) -> dict[str, Any]:
    """A valid published event as the outbox relay renders it."""
    return {
        "id": "4f3c2b1a-0000-4000-8000-000000000001",
        "specversion": "1.0",
        "type": "item.created",
        "source": "/services/items-api",
        "subject": ITEM_ID,
        "time": "2026-10-28T12:00:00+00:00",
        "datacontenttype": "application/json",
        "data": {"item": {"id": ITEM_ID, "name": "spool", "quantity": 1}},
        **overrides,
    }
