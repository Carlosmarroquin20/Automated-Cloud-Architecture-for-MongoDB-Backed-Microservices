"""OpenTelemetry tracing configuration.

Tracing is opt-in through configuration so the default footprint stays minimal:
with tracing disabled no tracer provider or exporter is created and no spans are
produced. When enabled, a tracer provider is installed with a service-identifying
resource, spans are exported over OTLP to the configured collector (and,
optionally, to the console), and the FastAPI and PyMongo integrations emit HTTP
request and database spans. This completes the three observability signals
alongside the existing metrics and structured logs.
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
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app import __version__
from app.core.config import Settings

logger = logging.getLogger(__name__)

# Probe and scrape endpoints are excluded so health checks and metrics polling do
# not generate a continuous stream of uninformative spans.
_EXCLUDED_URLS = "health/live,health/ready,metrics"

# Guards against double instrumentation, which would attach duplicate spans.
_instrumented = False


def configure_tracing(app: FastAPI, settings: Settings) -> None:
    """Install the tracer provider and instrument the app when tracing is enabled."""
    global _instrumented
    if not settings.otel_enabled or _instrumented:
        return

    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": __version__,
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
    if settings.otel_console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_EXCLUDED_URLS)
    PymongoInstrumentor().instrument(tracer_provider=provider)

    _instrumented = True
    logger.info(
        "tracing enabled",
        extra={"otlp_endpoint": settings.otel_exporter_otlp_endpoint or "console-only"},
    )
