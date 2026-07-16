"""POST /detect/stream, DELETE /detect/stream/{camera_id}, GET /detect/stream
— start/stop/list live per-camera streaming (webcam/USB/RTSP/IP camera/directory).

Starting/stopping a stream is an operational action (OPERATOR+); listing
active streams needs only an authenticated principal (VIEWER+).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from sentinel_detect.api.dependencies.auth import CurrentUserDep, require_role
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.api.dependencies.streaming import StreamManagerDep
from sentinel_detect.api.schemas.stream import StartStreamRequest, StreamStatusResponse
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.core.exceptions import ConfigurationError
from sentinel_detect.database.repositories import CameraRepository
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/detect", tags=["streaming"])


@router.get("/stream", response_model=list[StreamStatusResponse])
async def list_streams(
    stream_manager: StreamManagerDep, _user: CurrentUserDep
) -> list[StreamStatusResponse]:
    """List currently active live camera streams and their per-stream
    frame count/last error. Requires any authenticated principal."""
    return [
        StreamStatusResponse(
            camera_id=status_.camera_id,
            started_at=status_.started_at,
            frames_processed=status_.frames_processed,
            last_error=status_.last_error,
        )
        for status_ in stream_manager.list_active()
    ]


@router.post("/stream", status_code=status.HTTP_202_ACCEPTED)
async def start_stream(
    payload: StartStreamRequest,
    session: DbSessionDep,
    stream_manager: StreamManagerDep,
    user: Annotated[User, Depends(require_role(UserRole.OPERATOR))],
) -> dict[str, str]:
    """Start an indefinitely-running live stream for a registered camera —
    the same detection → tracking → event → alert → storage pipeline
    `POST /detect/video` uses, run against a webcam/USB/RTSP/IP-camera feed
    or a polled directory of images instead of a bounded file upload.
    Requires OPERATOR+. 404 if the camera doesn't exist, 400 if it's
    disabled, 409 if it's already streaming. Frames stream live over
    `WS /ws/stream/{camera_id}`.
    """
    camera = await CameraRepository(session).get(payload.camera_id)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"camera '{payload.camera_id}' not found",
        )
    if not camera.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"camera '{payload.camera_id}' is disabled",
        )

    try:
        await stream_manager.start(camera)
    except ConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    logger.info("stream_started", camera_id=camera.id, by_user=user.username)  # audit log
    return {"camera_id": camera.id, "status": "started"}


@router.delete("/stream/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_stream(
    camera_id: str,
    stream_manager: StreamManagerDep,
    user: Annotated[User, Depends(require_role(UserRole.OPERATOR))],
) -> None:
    """Stop a live camera stream. Requires OPERATOR+. 404s if that camera
    isn't currently streaming."""
    try:
        await stream_manager.stop(camera_id)
    except ConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    logger.info("stream_stopped", camera_id=camera_id, by_user=user.username)  # audit log
