"""Hermetic integration test for POST /detect/video.

Deliberately doesn't assert on which tracks are found — that depends on
whether the 'vision' extra + real weights are available (see
test_detect_image_live.py for that end-to-end proof). This test proves the
video-decoding/multi-frame/tracking-service plumbing itself works: the
endpoint accepts a real (tiny, synthetic) video file, iterates its frames,
and returns a well-formed response either way.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from sentinel_detect.api.dependencies.pipeline import get_pipeline_service
from sentinel_detect.config.settings import EventRuleSettings, TrackingSettings
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.detector import BaseDetector
from sentinel_detect.events.detected import PersonDetectedRule
from sentinel_detect.main import app
from sentinel_detect.services.detection_service import DetectionService
from sentinel_detect.services.event_engine import EventEngine
from sentinel_detect.services.pipeline_service import PipelineService
from sentinel_detect.services.tracking_service import TrackingService
from sentinel_detect.tracking.byte_track import ByteTracker


class _FixedPersonDetector(BaseDetector):
    """Always reports one PERSON detection — deterministic stand-in for
    real inference, so track/event/alert/storage plumbing that only runs
    when *something* is actually detected can be exercised hermetically
    (real inference content is Phase 2/3's `test_detect_image_live.py`
    concern, not this file's)."""

    def detect(self, frame: Frame) -> list[Detection]:
        return [
            Detection(
                camera_id=frame.camera_id,
                detector="person",
                label=DetectionClass.PERSON,
                confidence=0.9,
                bbox=BoundingBox(x1=0, y1=0, x2=20, y2=20),
                frame_width=frame.width,
                frame_height=frame.height,
            )
        ]


def _make_synthetic_video(num_frames: int = 5) -> bytes:
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "synthetic.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
        for i in range(num_frames):
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            frame[:, :] = (i * 20, 0, 0)
            writer.write(frame)
        writer.release()
        return path.read_bytes()


def test_detect_video_processes_every_frame_and_returns_a_well_formed_response() -> None:
    video_bytes = _make_synthetic_video(num_frames=5)

    with TestClient(app) as client:
        response = client.post(
            "/detect/video",
            files={"file": ("clip.mp4", io.BytesIO(video_bytes), "video/mp4")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["frames_processed"] == 5
    assert isinstance(body["tracks"], list)
    assert isinstance(body["events"], list)
    assert isinstance(body["active_detectors"], list)
    assert isinstance(body["active_rules"], list)
    assert "loitering" in body["active_rules"]
    assert body["camera_id"].startswith("video-upload-")


def test_detect_video_rejects_a_non_video_file() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/detect/video",
            files={"file": ("not_a_video.txt", io.BytesIO(b"hello world"), "text/plain")},
        )

    assert response.status_code == 400


def test_detect_video_rejects_invalid_regions_json() -> None:
    video_bytes = _make_synthetic_video(num_frames=2)

    with TestClient(app) as client:
        response = client.post(
            "/detect/video",
            files={"file": ("clip.mp4", io.BytesIO(video_bytes), "video/mp4")},
            data={"regions_json": "not json"},
        )

    assert response.status_code == 400


def test_detect_video_accepts_well_formed_regions_json() -> None:
    video_bytes = _make_synthetic_video(num_frames=2)
    regions_json = (
        '[{"id": "r1", "camera_id": "cam-x", "name": "Zone", "type": "restricted_zone", '
        '"polygon": {"points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}]}}]'
    )

    with TestClient(app) as client:
        response = client.post(
            "/detect/video",
            files={"file": ("clip.mp4", io.BytesIO(video_bytes), "video/mp4")},
            data={"regions_json": regions_json},
        )

    assert response.status_code == 200


def test_detect_video_response_reports_consistent_storage_counts() -> None:
    """Storage stage: whatever the pipeline produced was actually committed.

    Doesn't assert specific counts (depends on real detections — see
    test_detect_image_live.py for that), just that the endpoint's own
    accounting is internally consistent and the commit didn't error.
    """
    video_bytes = _make_synthetic_video(num_frames=3)

    with TestClient(app) as client:
        response = client.post(
            "/detect/video",
            files={"file": ("clip.mp4", io.BytesIO(video_bytes), "video/mp4")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["detections_stored"] >= 0
    assert body["events_stored"] == len(body["events"])
    if body["events_stored"] == 0:
        assert body["alerts_stored"] == 0


def test_app_database_session_factory_persists_a_real_row() -> None:
    """Proves the app's real, wired-up `db_session_factory` (built in
    main.py's lifespan from whatever AppSettings.database.url resolves to)
    is a genuine working async SQLAlchemy session factory — independent of
    whether the ML pipeline actually produces any detections."""
    import asyncio

    from sentinel_detect.core.entities.detection import Detection, DetectionClass
    from sentinel_detect.core.entities.geometry import BoundingBox
    from sentinel_detect.database.repositories import DetectionRepository

    async def _seed_and_fetch(session_factory: object) -> Detection | None:
        async with session_factory() as session:  # type: ignore[operator]
            repo = DetectionRepository(session)
            detection = Detection(
                camera_id="integration-test-cam",
                detector="person",
                label=DetectionClass.PERSON,
                confidence=0.99,
                bbox=BoundingBox(x1=0, y1=0, x2=5, y2=5),
                frame_width=64,
                frame_height=64,
            )
            await repo.create(detection)
            await session.commit()
            return await repo.get(detection.id)

    with TestClient(app) as client:
        session_factory = client.app.state.db_session_factory  # type: ignore[attr-defined]
        fetched = asyncio.run(_seed_and_fetch(session_factory))

    assert fetched is not None
    assert fetched.camera_id == "integration-test-cam"


def test_detect_video_with_a_real_detection_produces_tracks_events_and_storage() -> None:
    """Overrides the real app's `PipelineService` dependency (FastAPI's own
    `app.dependency_overrides` mechanism, not a patched module) with one
    built from a deterministic fake detector — proving track accumulation,
    event dispatch, and the persistence loops all work end-to-end when a
    detection genuinely occurs, independent of whether real ML inference
    happens to find anything in this synthetic footage."""
    detector = _FixedPersonDetector(None, confidence_threshold=0.1, iou_threshold=0.5)  # type: ignore[arg-type]
    detection_service = DetectionService({"person": detector})
    tracker = ByteTracker(TrackingSettings(min_hits=1))
    tracking_service = TrackingService(detection_service, tracker)
    rules = {"person_detected": PersonDetectedRule(EventRuleSettings(cooldown_seconds=0.0))}
    fake_pipeline_service = PipelineService(tracking_service, EventEngine(rules))

    video_bytes = _make_synthetic_video(num_frames=3)
    app.dependency_overrides[get_pipeline_service] = lambda: fake_pipeline_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/detect/video",
                files={"file": ("clip.mp4", io.BytesIO(video_bytes), "video/mp4")},
            )
    finally:
        del app.dependency_overrides[get_pipeline_service]

    assert response.status_code == 200
    body = response.json()
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["label"] == "person"
    assert body["tracks"][0]["frames_tracked"] == 3
    assert len(body["events"]) >= 1
    assert body["detections_stored"] == 3
    assert body["events_stored"] == len(body["events"])


def test_detect_image_rejects_undecodable_bytes() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/detect/image",
            files={
                "file": ("not_an_image.jpg", io.BytesIO(b"not actually an image"), "image/jpeg")
            },
        )

    assert response.status_code == 400
