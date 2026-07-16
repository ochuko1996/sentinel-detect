"""GET /detections — query stored raw detections, optionally filtered by camera."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from sentinel_detect.api.dependencies.auth import CurrentUserDep
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.database.repositories import DetectionRepository

router = APIRouter(tags=["detections"])


@router.get("/detections", response_model=list[Detection])
async def list_detections(
    session: DbSessionDep,
    _user: CurrentUserDep,
    camera_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Detection]:
    """List stored raw detections (per-object, per-frame boxes — not
    rule-engine events), newest first, optionally filtered by `camera_id`.
    Requires any authenticated principal."""
    repo = DetectionRepository(session)
    if camera_id:
        return await repo.list_by_camera(camera_id, offset=offset, limit=limit)
    return await repo.list(offset=offset, limit=limit)
