"""FastAPI dependency providers for the alert engine and its store.

Both are built once in `main.py`'s lifespan and stashed on `app.state`;
these dependencies just retrieve them per-request. `ConnectionManager` has
no HTTP dependency provider — the `WS /ws/alerts` route reads it directly
off `websocket.app.state` (see `api/routers/websocket.py` for why).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from sentinel_detect.alerts import AlertStore
from sentinel_detect.services.alert_engine import AlertEngine


def get_alert_engine(request: Request) -> AlertEngine:
    engine: AlertEngine = request.app.state.alert_engine
    return engine


def get_alert_store(request: Request) -> AlertStore:
    store: AlertStore = request.app.state.alert_store
    return store


AlertEngineDep = Annotated[AlertEngine, Depends(get_alert_engine)]
AlertStoreDep = Annotated[AlertStore, Depends(get_alert_store)]
