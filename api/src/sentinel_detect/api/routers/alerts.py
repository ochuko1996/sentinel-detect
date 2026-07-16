"""GET /alerts — recent alerts from the in-memory REST alert channel store.

Backed by `AlertStore` (`alerts/rest_channel.py`) — a bounded in-memory
deque, not the database, so it's always available with zero setup but
doesn't survive a restart (every alert is *also* durably persisted as an
`AlertRecord` via the database layer; this endpoint is the fast, always-on
path, not the only one). Only returns anything once the `rest` alert
channel is enabled (it is, by default) and at least one event has been
dispatched through `AlertEngine`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from sentinel_detect.api.dependencies.alerts import AlertStoreDep
from sentinel_detect.api.schemas.events import EventSummary

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[EventSummary])
async def list_alerts(
    store: AlertStoreDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[EventSummary]:
    """Most recent alerts, newest first, from the in-memory REST store.
    Unauthenticated (see docs/architecture.md for why). For a live push
    feed instead of polling, see `WS /ws/alerts`.
    """
    return [EventSummary.from_event(event) for event in store.recent(limit)]
