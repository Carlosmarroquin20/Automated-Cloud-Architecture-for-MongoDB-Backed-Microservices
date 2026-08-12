"""Application entry point and composition root."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health, meta, metrics
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.metrics import set_app_info
from app.db.mongodb import MongoDB
from app.middleware.metrics import MetricsMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)

_DESCRIPTION = (
    "Asynchronous FastAPI microservice with resilient MongoDB Atlas persistence, "
    "structured JSON logging, health probes, and Prometheus metrics."
)
_CONTACT: dict[str, Any] = {
    "name": "Project repository",
    "url": "https://github.com/Carlosmarroquin20/Automated-Cloud-Architecture-for-MongoDB-Backed-Microservices",
}
_LICENSE: dict[str, Any] = {"name": "MIT"}
_OPENAPI_TAGS: list[dict[str, Any]] = [
    {"name": "items", "description": "Create, read, update, and delete items."},
    {"name": "health", "description": "Liveness and readiness probes."},
    {"name": "meta", "description": "Service metadata."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    mongodb = MongoDB(settings)
    await mongodb.connect()
    app.state.mongodb = mongodb

    if mongodb.is_connected:
        try:
            await ItemRepository(mongodb.database).ensure_indexes()
        except Exception as exc:
            # Index creation is best-effort at startup; the service remains
            # operational and indexing is retried on subsequent deployments.
            logger.warning("index initialization skipped", extra={"error": str(exc)})

    logger.info(
        "service startup complete",
        extra={
            "app_env": settings.app_env,
            "version": __version__,
            "mongodb_connected": mongodb.is_connected,
        },
    )
    try:
        yield
    finally:
        await mongodb.disconnect()
        logger.info("service shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    set_app_info(settings.app_name, __version__, settings.app_env)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=_DESCRIPTION,
        contact=_CONTACT,
        license_info=_LICENSE,
        openapi_tags=_OPENAPI_TAGS,
        # Interactive documentation is disabled in production to reduce the
        # exposed surface; it remains available in non-production environments.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Restrictive CORS by default; allowed origins are supplied per environment.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Instruments request count, latency, and the in-flight gauge for Prometheus.
    app.add_middleware(MetricsMiddleware)
    # Added last so it wraps the stack and assigns a correlation identifier before
    # any downstream processing.
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(meta.router)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    runtime_settings = get_settings()
    # Binding to all interfaces is required for ingress within a container
    # network; external exposure is governed by Kubernetes services and network
    # policies rather than the process itself.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104
        port=runtime_settings.app_port,
        log_config=None,
    )
