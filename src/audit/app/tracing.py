"""Opt-in OpenTelemetry tracing.

Disabled by default, so no provider or exporter exists and no spans are produced.
When enabled, the service reports under its own name; consumed events continue
the trace carried in each message, so a single trace spans the request that
changed an item, the relay's publish, and this service's processing.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app import __version__
from app.config import Settings

logger = logging.getLogger(__name__)

_EXCLUDED_URLS = "health/live,health/ready,metrics"
_instrumented = False


def configure_tracing(app: FastAPI, settings: Settings) -> None:
    global _instrumented
    if not settings.otel_enabled or _instrumented:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": __version__,
                "deployment.environment": settings.app_env,
            }
        )
    )
    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_EXCLUDED_URLS)
    PymongoInstrumentor().instrument(tracer_provider=provider)
    _instrumented = True
    logger.info("tracing enabled", extra={"service_name": settings.app_name})
