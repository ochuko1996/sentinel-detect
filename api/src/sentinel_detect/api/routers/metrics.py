"""GET /metrics — Prometheus text-format metrics.

Deliberately unauthenticated, matching `/health`: Prometheus scrapers
typically can't do an OAuth2 login flow, and network-level access control
(not app-level auth) is the standard way to protect a scrape endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST
from starlette.responses import Response

from sentinel_detect.utils.metrics import render_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus text-format metrics. Unauthenticated and rate-limit-exempt
    (scrapers can't do an OAuth2 flow; protect this at the network level)."""
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
