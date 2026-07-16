"""Integration tests for CORS: the sentinel-detect-console client (a
separate origin, e.g. http://localhost:3000) needs real CORS headers to
call this API from a browser — added once that client actually needed it.

Builds a fresh `create_app()` under a controlled `cors_origins` setting
rather than using the shared `app` singleton, since CORS behavior depends
on exactly what's configured.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_detect.config.settings import get_settings
from sentinel_detect.main import create_app


def test_an_allowed_origin_gets_cors_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_SECURITY__CORS_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_a_disallowed_origin_gets_no_cors_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_SECURITY__CORS_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health", headers={"Origin": "http://evil.example.com"})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_a_preflight_request_is_answered_for_an_allowed_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINEL_SECURITY__CORS_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.options(
                "/cameras",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_a_429_from_the_rate_limiter_still_carries_cors_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CORSMiddleware must be outermost — added last — or a 429 short-circuit
    from RateLimitMiddleware would reach the browser with no CORS header,
    which shows up as a misleading "CORS error" instead of the real 429."""
    monkeypatch.setenv("SENTINEL_SECURITY__CORS_ORIGINS", '["http://localhost:3000"]')
    monkeypatch.setenv("SENTINEL_SECURITY__RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            client.get("/cameras", headers={"Origin": "http://localhost:3000"})
            limited = client.get("/cameras", headers={"Origin": "http://localhost:3000"})
    finally:
        get_settings.cache_clear()

    assert limited.status_code == 429
    assert limited.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_middleware_is_skipped_entirely_when_no_origins_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINEL_SECURITY__CORS_ORIGINS", "[]")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
