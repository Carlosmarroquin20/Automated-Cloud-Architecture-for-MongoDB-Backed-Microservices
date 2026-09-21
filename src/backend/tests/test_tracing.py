"""Tests for the tracing configuration gate.

The enabled path installs a process-global tracer provider and instruments
PyMongo globally, so these tests exercise only the default disabled path, which
must remain a no-op. The enabled path is verified against a live collector.
"""

from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import Settings
from app.core.tracing import configure_tracing


def test_tracing_disabled_installs_no_sdk_provider() -> None:
    app = FastAPI()
    configure_tracing(app, Settings(otel_enabled=False))
    # With tracing disabled the global provider stays the API default rather than
    # a real SDK provider, so no spans are produced.
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)


def test_tracing_disabled_is_idempotent() -> None:
    app = FastAPI()
    settings = Settings(otel_enabled=False)
    configure_tracing(app, settings)
    configure_tracing(app, settings)
