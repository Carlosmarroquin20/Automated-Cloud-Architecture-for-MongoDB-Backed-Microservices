"""Request-scoped context propagated to structured logs for traceability."""

from __future__ import annotations

from contextvars import ContextVar

# Correlation identifier bound per request and emitted on every log record to
# enable end-to-end tracing across distributed log aggregation.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str:
    return _request_id.get()
