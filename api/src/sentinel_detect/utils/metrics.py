"""Prometheus metrics: HTTP request counters/latency (via middleware) plus
pipeline counters (detections/events/alerts) incremented where the pipeline
actually produces them (`api/routers/detect.py`'s storage stage) — real
instrumentation of real activity, not placeholder gauges.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

HTTP_REQUESTS_TOTAL = Counter(
    "sentinel_http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "sentinel_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
DETECTIONS_TOTAL = Counter(
    "sentinel_detections_total", "Total detections produced", ["detector"]
)
EVENTS_TOTAL = Counter("sentinel_events_total", "Total events raised", ["rule"])
ALERTS_TOTAL = Counter(
    "sentinel_alerts_total", "Total alert dispatch attempts", ["channel", "status"]
)


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        path = request.url.path
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method, path=path, status_code=response.status_code
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(elapsed)
        return response


def render_metrics() -> bytes:
    return generate_latest()
