"""Prometheus metric definitions.

Metrics are registered on the default collector registry at import time. Route
templates rather than raw paths are used as labels to bound label cardinality.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)
REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being served.",
    ["method"],
)
APP_INFO = Info("app", "Static application metadata.")


def set_app_info(name: str, version: str, environment: str) -> None:
    APP_INFO.info({"name": name, "version": version, "environment": environment})
