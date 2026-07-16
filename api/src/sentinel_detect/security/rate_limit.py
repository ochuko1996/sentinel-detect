"""In-memory sliding-window rate limiting middleware.

Keyed by API key (if the caller sent one) else client IP — a caller's JWT
identity isn't available this early in the ASGI stack without decoding the
token a second time outside the normal dependency system, so IP/API-key is
the practical key for a request-level limiter.

Per-request pruning (dropping timestamps older than the window) only
touches the *current* caller's key, so a key that simply stops being seen
would otherwise keep its entry forever — unbounded memory growth over a
long-running process with many distinct callers. A periodic full sweep
(`_maybe_sweep`, every `_SWEEP_INTERVAL_SECONDS`) drops any key whose
newest hit has already aged out of the window, which is enough to bound
memory without a real LRU structure — this middleware only needs "don't
grow forever," not "evict the least-recently-used key first."
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from sentinel_detect.config.settings import SecuritySettings

_WINDOW_SECONDS = 60.0
_SWEEP_INTERVAL_SECONDS = 300.0
_EXEMPT_PATHS = frozenset({"/health", "/metrics", "/docs", "/openapi.json", "/redoc"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: SecuritySettings) -> None:
        super().__init__(app)
        self._limit = settings.rate_limit_per_minute
        self._api_key_header = settings.api_key_header
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        key = request.headers.get(self._api_key_header) or (
            request.client.host if request.client else "unknown"
        )
        now = time.monotonic()
        self._maybe_sweep(now)

        hits = self._hits[key]
        while hits and now - hits[0] > _WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= self._limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": "60"},
            )

        hits.append(now)
        return await call_next(request)

    def _maybe_sweep(self, now: float) -> None:
        if now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep = now
        stale_keys = [
            key for key, hits in self._hits.items() if not hits or now - hits[-1] > _WINDOW_SECONDS
        ]
        for key in stale_keys:
            del self._hits[key]
