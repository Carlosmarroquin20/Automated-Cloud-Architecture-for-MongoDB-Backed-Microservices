"""Asynchronous MongoDB connectivity with resilient startup semantics.

The native PyMongo asynchronous client is used in preference to Motor, which is
deprecated. TLS is enforced by the Atlas SRV connection string. Client creation
performs no network I/O; connectivity is validated through an explicit ping with
bounded exponential backoff and full jitter so that transient unavailability does
not crash the process and is instead surfaced through readiness gating.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings

if TYPE_CHECKING:
    from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)

# Upper bound on backoff to prevent unbounded startup delay under sustained
# database unavailability.
_MAX_BACKOFF_SECONDS = 10.0


def _jittered(ceiling: float) -> float:
    """Return a full-jitter delay drawn uniformly from ``[0, ceiling]``.

    Replicas restarted together, as in a rollout or a node failure, would retry in
    lockstep under a deterministic schedule and reach the database as synchronized
    bursts; randomizing the whole interval spreads those attempts out.
    """
    # Jitter is a scheduling concern with no security property, so the standard
    # pseudo-random generator is adequate.
    return random.uniform(0.0, ceiling)  # noqa: S311


class MongoDB:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncMongoClient[dict[str, Any]] | None = None
        self._database: AsyncDatabase[dict[str, Any]] | None = None
        self._connected = False

    async def connect(self) -> None:
        self._client = AsyncMongoClient(
            self._settings.mongodb_uri.get_secret_value(),
            serverSelectionTimeoutMS=self._settings.mongodb_server_selection_timeout_ms,
            connectTimeoutMS=self._settings.mongodb_connect_timeout_ms,
            socketTimeoutMS=self._settings.mongodb_socket_timeout_ms,
            maxPoolSize=self._settings.mongodb_max_pool_size,
            minPoolSize=self._settings.mongodb_min_pool_size,
            retryWrites=True,
            tz_aware=True,
            uuidRepresentation="standard",
            appname=self._settings.app_name,
        )
        self._database = self._client[self._settings.mongodb_db_name]

        if self._settings.mongodb_ping_on_startup:
            self._connected = await self._ping_with_retries()

    async def _ping_with_retries(self) -> bool:
        client = self._client
        if client is None:
            return False

        max_retries = self._settings.mongodb_connect_max_retries
        ceiling = self._settings.mongodb_connect_retry_base_delay_seconds

        for attempt in range(max_retries + 1):
            try:
                await client.admin.command("ping")
                logger.info("mongodb connection established", extra={"attempt": attempt + 1})
                return True
            except PyMongoError as exc:
                if attempt >= max_retries:
                    logger.error(
                        "mongodb connection failed after retries",
                        extra={"attempts": attempt + 1, "error": str(exc)},
                    )
                    return False
                delay = _jittered(ceiling)
                logger.warning(
                    "mongodb connection attempt failed; retrying",
                    extra={
                        "attempt": attempt + 1,
                        "retry_in_seconds": round(delay, 3),
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(delay)
                ceiling = min(ceiling * 2, _MAX_BACKOFF_SECONDS)

        return False

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._database = None
            self._connected = False

    @property
    def database(self) -> AsyncDatabase[dict[str, Any]]:
        if self._database is None:
            raise RuntimeError("MongoDB is not connected")
        return self._database

    @property
    def is_connected(self) -> bool:
        return self._connected
