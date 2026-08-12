"""Prometheus metrics endpoint and instrumentation tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    with TestClient(app) as client:
        client.get("/health/live")
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert 'path="/health/live"' in body


def test_metrics_use_route_template_not_raw_path(client: TestClient) -> None:
    # A concrete identifier must be collapsed to its route template so that the
    # metric label space stays bounded.
    client.get("/api/v1/items/000000000000000000000000")
    response = client.get("/metrics")
    assert 'path="/api/v1/items/{item_id}"' in response.text
