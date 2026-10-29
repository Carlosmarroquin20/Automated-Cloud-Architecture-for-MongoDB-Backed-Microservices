"""Audit service entry point and composition root."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from app import __version__
from app.api import health_router, router
from app.config import get_settings
from app.consumer import AuditConsumer
from app.logs import configure_logging
from app.repository import AuditRepository
from app.tracing import configure_tracing

logger = logging.getLogger(__name__)

# Bounded so a consumer blocked in a fetch cannot delay shutdown past the
# orchestrator's grace period.
_CONSUMER_STOP_TIMEOUT_SECONDS = 10.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Client creation performs no network I/O; the consumer retries the first
    # database and broker contact itself, so startup never blocks on either.
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        socketTimeoutMS=settings.mongodb_socket_timeout_ms,
        tz_aware=True,
        appname=settings.app_name,
    )
    repository = AuditRepository(client[settings.mongodb_db_name])
    app.state.mongo_client = client
    app.state.repository = repository

    stop = asyncio.Event()
    consumer = AuditConsumer(settings, repository) if settings.consumer_enabled else None
    app.state.consumer = consumer
    task = asyncio.create_task(consumer.run(stop)) if consumer is not None else None
    logger.info(
        "service startup complete",
        extra={"version": __version__, "consumer_enabled": settings.consumer_enabled},
    )
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(task, timeout=_CONSUMER_STOP_TIMEOUT_SECONDS)
        await client.close()
        logger.info("service shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Consumes item domain events and serves each item's audit history.",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(router, prefix=settings.api_v1_prefix)
    configure_tracing(app, settings)
    return app


app = create_app()
