import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinel_detect.config.settings import SecuritySettings
from sentinel_detect.security import rate_limit as rate_limit_module
from sentinel_detect.security.rate_limit import RateLimitMiddleware


def _make_app(limit: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=SecuritySettings(rate_limit_per_minute=limit))

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_requests_within_the_limit_all_succeed() -> None:
    client = TestClient(_make_app(limit=3))
    for _ in range(3):
        assert client.get("/ping").status_code == 200


def test_requests_beyond_the_limit_are_rejected_with_429() -> None:
    client = TestClient(_make_app(limit=2))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200

    response = client.get("/ping")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_exempt_paths_are_never_rate_limited() -> None:
    client = TestClient(_make_app(limit=1))
    client.get("/ping")  # consume the only allowed hit

    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_different_api_keys_get_independent_limits() -> None:
    client = TestClient(_make_app(limit=1))

    assert client.get("/ping", headers={"X-API-Key": "key-a"}).status_code == 200
    assert client.get("/ping", headers={"X-API-Key": "key-b"}).status_code == 200
    assert client.get("/ping", headers={"X-API-Key": "key-a"}).status_code == 429


def test_periodic_sweep_evicts_keys_that_have_gone_completely_quiet() -> None:
    app = FastAPI()
    middleware = RateLimitMiddleware(app, settings=SecuritySettings(rate_limit_per_minute=5))
    middleware._hits["quiet-key"].append(0.0)  # its only hit, long since outside the window
    middleware._last_sweep = 0.0

    middleware._maybe_sweep(now=1000.0)  # well past both the window and the sweep interval

    assert "quiet-key" not in middleware._hits


def test_periodic_sweep_leaves_a_key_with_hits_still_inside_the_window() -> None:
    app = FastAPI()
    middleware = RateLimitMiddleware(app, settings=SecuritySettings(rate_limit_per_minute=5))
    middleware._hits["active-key"].append(995.0)  # recent relative to `now=1000.0`
    middleware._last_sweep = 0.0

    middleware._maybe_sweep(now=1000.0)

    assert "active-key" in middleware._hits


def test_sweep_does_nothing_before_the_sweep_interval_elapses() -> None:
    app = FastAPI()
    middleware = RateLimitMiddleware(app, settings=SecuritySettings(rate_limit_per_minute=5))
    middleware._hits["quiet-key"].append(0.0)
    middleware._last_sweep = 999.0

    middleware._maybe_sweep(now=1000.0)  # only 1s since the last sweep

    assert "quiet-key" in middleware._hits


def test_per_request_pruning_lets_a_hit_that_has_aged_out_be_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sliding window actually slides: once a caller's one hit is older
    than the (here, shortened) window, the *next* request re-checks the
    limit fresh rather than treating that stale hit as still counting."""
    monkeypatch.setattr(rate_limit_module, "_WINDOW_SECONDS", 0.05)
    client = TestClient(_make_app(limit=1))

    assert client.get("/ping").status_code == 200  # consumes the only slot
    time.sleep(0.1)  # past the shortened window
    assert client.get("/ping").status_code == 200  # the old hit has aged out
