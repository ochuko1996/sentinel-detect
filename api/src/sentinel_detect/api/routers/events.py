"""GET /events — query stored events, optionally filtered by camera."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from sentinel_detect.api.dependencies.auth import CurrentUserDep
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.api.schemas.events import EventSummary
from sentinel_detect.database.repositories import EventRepository

router = APIRouter(tags=["events"])


@router.get("/events", response_model=list[EventSummary])
async def list_events(
    session: DbSessionDep,
    _user: CurrentUserDep,
    camera_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EventSummary]:
    """List stored events (rule-engine detections like person_detected,
    loitering, restricted_area_intrusion, ...), newest first, optionally
    filtered by `camera_id`. Requires any authenticated principal."""
    repo = EventRepository(session)
    events = (
        await repo.list_by_camera(camera_id, offset=offset, limit=limit)
        if camera_id
        else await repo.list(offset=offset, limit=limit)
    )
    return [EventSummary.from_event(event) for event in events]
