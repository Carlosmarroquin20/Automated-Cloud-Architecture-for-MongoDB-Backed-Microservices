"""HTTP metrics instrumentation middleware."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY, REQUESTS_IN_PROGRESS

# The scrape endpoint is excluded so that observability polling does not inflate
# application traffic metrics.
METRICS_PATH = "/metrics"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == METRICS_PATH:
            return await call_next(request)

        method = request.method
        REQUESTS_IN_PROGRESS.labels(method=method).inc()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Recorded on both success and failure to preserve metric fidelity.
            elapsed = time.perf_counter() - start
            path = _path_label(request)
            REQUEST_COUNT.labels(method=method, path=path, status=str(status)).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)
            REQUESTS_IN_PROGRESS.labels(method=method).dec()


def _path_label(request: Request) -> str:
    # The full templated path (for example "/api/v1/items/{item_id}") is
    # reconstructed from the resolved path parameters so that identifier values
    # are collapsed to their placeholders, bounding label cardinality. Nested
    # routers do not expose the fully-prefixed template on the matched route,
    # so the URL path is used as the reconstruction base.
    scope = request.scope
    if scope.get("route") is None and scope.get("endpoint") is None:
        return "unmatched"
    path = request.url.path
    params: dict[str, object] = scope.get("path_params") or {}
    for key, value in params.items():
        path = path.replace(str(value), "{" + key + "}", 1)
    return path
