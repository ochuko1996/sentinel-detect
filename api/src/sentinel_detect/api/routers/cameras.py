"""Camera CRUD: GET /cameras, GET /cameras/{id}, POST /camera, PUT /camera/{id},
DELETE /camera/{id}.

Read access requires any authenticated principal (VIEWER+); create/update
require OPERATOR+; delete requires ADMIN (the most destructive action gets
the highest bar).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sentinel_detect.api.dependencies.auth import CurrentUserDep, require_role
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.api.schemas.camera import CameraCreateRequest, CameraUpdateRequest
from sentinel_detect.core.entities.camera import Camera
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.database.repositories import CameraRepository
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["cameras"])


@router.get("/cameras", response_model=list[Camera])
async def list_cameras(
    session: DbSessionDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Camera]:
    """List configured cameras, paginated. Requires any authenticated principal."""
    return await CameraRepository(session).list(offset=offset, limit=limit)


@router.get("/cameras/{camera_id}", response_model=Camera)
async def get_camera(camera_id: str, session: DbSessionDep, _user: CurrentUserDep) -> Camera:
    """Fetch one camera by id. Requires any authenticated principal."""
    camera = await CameraRepository(session).get(camera_id)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"camera '{camera_id}' not found"
        )
    return camera


@router.post("/camera", response_model=Camera, status_code=status.HTTP_201_CREATED)
async def create_camera(
    payload: CameraCreateRequest,
    session: DbSessionDep,
    user: Annotated[User, Depends(require_role(UserRole.OPERATOR))],
) -> Camera:
    """Register a new camera. Requires OPERATOR+. 409s if `id` already exists."""
    repo = CameraRepository(session)
    if await repo.get(payload.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"camera '{payload.id}' already exists"
        )

    camera = Camera(**payload.model_dump())
    await repo.create(camera)
    await session.commit()
    logger.info("camera_created", camera_id=camera.id, by_user=user.username)  # audit log
    return camera


@router.put("/camera/{camera_id}", response_model=Camera)
async def update_camera(
    camera_id: str,
    payload: CameraUpdateRequest,
    session: DbSessionDep,
    user: Annotated[User, Depends(require_role(UserRole.OPERATOR))],
) -> Camera:
    """Partially update a camera — only fields set in the request body
    change. Requires OPERATOR+. 404s if `camera_id` doesn't exist."""
    repo = CameraRepository(session)
    existing = await repo.get(camera_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"camera '{camera_id}' not found"
        )

    updates = payload.model_dump(exclude_unset=True)
    updated = existing.model_copy(update=updates)
    await repo.update(updated)
    await session.commit()
    logger.info(
        "camera_updated", camera_id=camera_id, by_user=user.username, fields=list(updates)
    )  # audit log
    return updated


@router.delete("/camera/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: str,
    session: DbSessionDep,
    user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> None:
    """Delete a camera. Requires ADMIN — the most destructive camera action
    gets the highest bar. 404s if `camera_id` doesn't exist."""
    repo = CameraRepository(session)
    try:
        await repo.delete(camera_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    logger.info("camera_deleted", camera_id=camera_id, by_user=user.username)  # audit log
