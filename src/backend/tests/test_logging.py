"""Structured JSON logging tests."""

from __future__ import annotations

import json
import logging
import sys

from app.core.context import set_request_id
from app.core.logging import JsonFormatter


def _make_record(level: int = logging.INFO, message: str = "message") -> logging.LogRecord:
    return logging.LogRecord("service", level, __file__, 10, message, None, None)


def test_formatter_emits_expected_fields() -> None:
    set_request_id("req-123")
    payload = json.loads(JsonFormatter().format(_make_record()))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "service"
    assert payload["message"] == "message"
    assert payload["request_id"] == "req-123"
    assert "timestamp" in payload


def test_formatter_projects_extras_and_exception() -> None:
    record = _make_record(level=logging.ERROR, message="failure")
    record.correlation_hint = "abc"
    try:
        raise ValueError("boom")
    except ValueError:
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))
    assert payload["correlation_hint"] == "abc"
    assert "boom" in payload["exception"]
