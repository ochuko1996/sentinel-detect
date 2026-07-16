"""POST /detect/image and POST /detect/video — run active detectors (and,
for video, tracking + the event rule engine) over an uploaded file."""

from __future__ import annotations

import asyncio
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import TypeAdapter, ValidationError

from sentinel_detect.api.dependencies.alerts import AlertEngineDep
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.api.dependencies.detection import DetectionServiceDep
from sentinel_detect.api.dependencies.pipeline import PipelineServiceDep
from sentinel_detect.api.schemas.detection import DetectImageResponse
from sentinel_detect.api.schemas.events import EventSummary
from sentinel_detect.api.schemas.tracking import DetectVideoResponse, TrackSummary
from sentinel_detect.core.entities.alert import Alert
from sentinel_detect.core.entities.camera import Region
from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.database.repositories import (
    AlertRepository,
    DetectionRepository,
    EventRepository,
)
from sentinel_detect.utils.logging import get_logger
from sentinel_detect.utils.metrics import ALERTS_TOTAL, DETECTIONS_TOTAL, EVENTS_TOTAL

logger = get_logger(__name__)
router = APIRouter(prefix="/detect", tags=["detection"])

_regions_adapter = TypeAdapter(list[Region])


@router.post("/image", response_model=DetectImageResponse)
async def detect_image(
    service: DetectionServiceDep,
    file: Annotated[UploadFile, File(description="Image file (JPEG/PNG/...)")],
    camera_id: Annotated[str, Form()] = "upload",
) -> DetectImageResponse:
    """Run every active detector over a single uploaded image.

    Single-frame, stateless — no tracking, no event rules, nothing
    persisted. Unauthenticated (see docs/architecture.md for why). Use
    `POST /detect/video` for tracking/events/storage, or `POST
    /detect/stream` for a live, indefinitely-running camera feed.
    """
    raw_bytes = await file.read()
    image_buffer = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="could not decode uploaded file as an image")

    frame = Frame(camera_id=camera_id, image=image, frame_index=0)

    started = time.monotonic()
    # Real inference is CPU/GPU-bound and can take tens of milliseconds;
    # running it directly in this coroutine would block every other
    # concurrent request (including live streams) for that long.
    detections = await asyncio.to_thread(service.detect, frame)
    elapsed_ms = (time.monotonic() - started) * 1000

    logger.info(
        "detect_image",
        camera_id=camera_id,
        detection_count=len(detections),
        elapsed_ms=round(elapsed_ms, 1),
    )

    return DetectImageResponse(
        camera_id=camera_id,
        frame_width=frame.width,
        frame_height=frame.height,
        detections=detections,
        active_detectors=service.active_detector_keys(),
    )


@dataclass
class _TrackAccumulator:
    """Folds every frame's `TrackedObject` for one track_id into a summary."""

    label: str
    first_seen_frame: int
    last_seen_frame: int
    frames_tracked: int
    last: TrackedObject

    @classmethod
    def start(cls, frame_index: int, tracked: TrackedObject) -> _TrackAccumulator:
        return cls(
            label=tracked.label.value,
            first_seen_frame=frame_index,
            last_seen_frame=frame_index,
            frames_tracked=1,
            last=tracked,
        )

    def observe(self, frame_index: int, tracked: TrackedObject) -> None:
        self.last_seen_frame = frame_index
        self.frames_tracked += 1
        self.last = tracked

    def to_summary(self, track_id: int) -> TrackSummary:
        return TrackSummary(
            track_id=track_id,
            label=self.label,
            first_seen_frame=self.first_seen_frame,
            last_seen_frame=self.last_seen_frame,
            frames_tracked=self.frames_tracked,
            last_bbox=self.last.bbox,
            last_confidence=self.last.confidence,
        )


@router.post("/video", response_model=DetectVideoResponse)
async def detect_video(
    pipeline_service: PipelineServiceDep,
    alert_engine: AlertEngineDep,
    session: DbSessionDep,
    file: Annotated[UploadFile, File(description="Video file (mp4/avi/mov/...)")],
    max_frames: Annotated[int, Query(ge=1, le=2000)] = 300,
    regions_json: Annotated[
        str | None,
        Form(
            description=(
                "Optional JSON array of Region objects (see core.entities.camera.Region) "
                "to exercise ROI-aware event rules against a one-shot upload, which has "
                "no registered camera to read regions from. A registered camera's own "
                "regions (POST /camera) are used automatically for a live stream instead."
            )
        ),
    ] = None,
) -> DetectVideoResponse:
    """Run the full detection → tracking → event → alert → storage pipeline
    over an uploaded video file, up to `max_frames`.

    A one-shot upload gets its own unique `camera_id` (`video-upload-<uuid>`)
    so concurrent uploads never share tracker state, and that state is
    reset when the request finishes. Persists every detection/event/alert
    produced in one transaction and returns per-track summaries, every
    event raised, and storage counts. Unauthenticated (see
    docs/architecture.md for why). For a live, indefinitely-running feed
    instead of a bounded upload, see `POST /detect/stream`.
    """
    regions: tuple[Region, ...] = ()
    if regions_json is not None:
        try:
            regions = tuple(_regions_adapter.validate_json(regions_json))
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=f"invalid regions_json: {exc}") from exc

    # Each upload is a one-shot camera_id: it must be unique per request (so
    # concurrent uploads don't share tracker state) and must be reset after
    # processing (so the tracker doesn't accumulate state forever for what
    # is, from the tracker's point of view, a camera that will never send
    # another frame).
    camera_id = f"video-upload-{uuid4()}"
    raw_bytes = await file.read()
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"

    track_summaries: dict[int, _TrackAccumulator] = {}
    all_detections: list[Detection] = []
    all_events: list[Event] = []
    all_alerts: list[Alert] = []
    frame_index = 0

    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(raw_bytes)
        tmp.flush()

        capture = cv2.VideoCapture(tmp.name)
        if not capture.isOpened():
            raise HTTPException(
                status_code=400, detail="could not open uploaded file as a video"
            )

        started = time.monotonic()
        try:
            while frame_index < max_frames:
                # Decoding and inference are both blocking, CPU-bound calls
                # (`cv2.VideoCapture.read`, real YOLO inference through the
                # tracker/event engine); up to `max_frames` of them run
                # per request, so this must not tie up the event loop for
                # the whole request's duration — same reasoning, and same
                # `asyncio.to_thread` pattern, as `StreamManager._run()`
                # uses for a live stream's per-frame loop.
                ok, image = await asyncio.to_thread(capture.read)
                if not ok:
                    break
                frame = Frame(camera_id=camera_id, image=image, frame_index=frame_index)
                detections, tracked_objects, events = await asyncio.to_thread(
                    pipeline_service.process_frame, frame, regions
                )
                all_detections.extend(detections)

                for tracked in tracked_objects:
                    existing = track_summaries.get(tracked.track_id)
                    if existing is None:
                        track_summaries[tracked.track_id] = _TrackAccumulator.start(
                            frame_index, tracked
                        )
                    else:
                        existing.observe(frame_index, tracked)

                if events:
                    all_alerts.extend(await alert_engine.dispatch(events))
                    all_events.extend(events)
                frame_index += 1
        finally:
            capture.release()
            pipeline_service.reset(camera_id)
    elapsed_ms = (time.monotonic() - started) * 1000

    # Storage stage: persist everything this run produced. Events must be
    # written before alerts, since AlertRecord.event_id is a real foreign
    # key into events — both repositories share this one session/transaction.
    detection_repo = DetectionRepository(session)
    event_repo = EventRepository(session)
    alert_repo = AlertRepository(session)
    for detection in all_detections:
        await detection_repo.create(detection)
        DETECTIONS_TOTAL.labels(detector=detection.detector).inc()
    for event in all_events:
        await event_repo.create(event)
        EVENTS_TOTAL.labels(rule=event.rule).inc()
    for alert in all_alerts:
        await alert_repo.create(alert)
        ALERTS_TOTAL.labels(channel=alert.channel.value, status=alert.status.value).inc()
    await session.commit()

    logger.info(
        "detect_video",
        camera_id=camera_id,
        frames_processed=frame_index,
        track_count=len(track_summaries),
        detection_count=len(all_detections),
        event_count=len(all_events),
        alert_count=len(all_alerts),
        elapsed_ms=round(elapsed_ms, 1),
    )

    return DetectVideoResponse(
        camera_id=camera_id,
        frames_processed=frame_index,
        active_detectors=pipeline_service.active_detector_keys(),
        active_rules=pipeline_service.active_rule_keys(),
        active_alert_channels=alert_engine.active_channel_keys(),
        tracks=[summary.to_summary(track_id) for track_id, summary in track_summaries.items()],
        events=[EventSummary.from_event(event) for event in all_events],
        detections_stored=len(all_detections),
        events_stored=len(all_events),
        alerts_stored=len(all_alerts),
    )
