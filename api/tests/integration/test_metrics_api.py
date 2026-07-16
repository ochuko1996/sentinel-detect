"""Integration test for GET /metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sentinel_detect.main import app


def test_metrics_endpoint_is_unauthenticated_and_returns_prometheus_text_format() -> None:
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # The HTTP request counters this same middleware maintains should
    # already show at least this one call to something.
    assert "sentinel_http_requests_total" in response.text


def test_metrics_reflects_real_http_request_counts() -> None:
    with TestClient(app) as client:
        client.get("/health")
        client.get("/health")
        response = client.get("/metrics")

    body = response.text
    assert 'path="/health"' in body
