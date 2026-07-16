"""Tests for StreamManager: real DirectoryVideoSource (no hardware needed),
real ByteTracker/EventEngine/AlertEngine, real temp-file SQLite persistence
— the full pipeline `POST /detect/video` uses, just run indefinitely in a
background task the way a live camera stream would be.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.alerts.rest_channel import AlertStore, RestAlertChannel
from sentinel_detect.alerts.websocket_channel import ConnectionManager
from sentinel_detect.config.settings import (
    AlertChannelSettings,
    DatabaseSettings,
    EventRuleSettings,
    PipelineSettings,
    TrackingSettings,
)
from sentinel_detect.core.entities.camera import Camera, SourceType
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.exceptions import ConfigurationError, VideoSourceError
from sentinel_detect.core.interfaces.detector import BaseDetector
from sentinel_detect.core.interfaces.video_source import BaseVideoSource
from sentinel_detect.database.engine import create_engine, create_session_factory, init_models
from sentinel_detect.database.repositories import DetectionRepository, EventRepository
from sentinel_detect.events.detected import PersonDetectedRule
from sentinel_detect.services.alert_engine import AlertEngine
from sentinel_detect.services.detection_service import DetectionService
from sentinel_detect.services.event_engine import EventEngine
from sentinel_detect.services.pipeline_service import PipelineService
from sentinel_detect.services.tracking_service import TrackingService
from sentinel_detect.streaming.broadcaster import StreamBroadcaster
from sentinel_detect.streaming.stream_manager import StreamManager, StreamStatus
from sentinel_detect.tracking.byte_track import ByteTracker


class _FixedPersonDetector(BaseDetector):
    """Always reports one PERSON detection at a fixed box — same precedent
    used to test TrackingService."""

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


def _build_real_pipeline() -> tuple[PipelineService, AlertEngine, AlertStore]:
    detector = _FixedPersonDetector(None, confidence_threshold=0.1, iou_threshold=0.5)  # type: ignore[arg-type]
    detection_service = DetectionService({"person": detector})
    tracker = ByteTracker(TrackingSettings(min_hits=1))
    tracking_service = TrackingService(detection_service, tracker)

    rules = {"person_detected": PersonDetectedRule(EventRuleSettings(cooldown_seconds=0.0))}
    event_engine = EventEngine(rules)
    pipeline_service = PipelineService(tracking_service, event_engine)

    alert_store = AlertStore()
    resources = AlertResources(connection_manager=ConnectionManager(), alert_store=alert_store)
    channel = RestAlertChannel(AlertChannelSettings(), resources)
    alert_engine = AlertEngine({"rest": channel})

    return pipeline_service, alert_engine, alert_store


def _build_empty_pipeline() -> tuple[PipelineService, AlertEngine]:
    """No detectors, no rules — nothing is ever detected/raised, so `_run()`
    never calls `_persist()`. Used by tests that need a real, running
    pipeline but must stay hermetic (no real DB session available)."""
    detection_service = DetectionService({})
    tracker = ByteTracker(TrackingSettings(min_hits=1))
    tracking_service = TrackingService(detection_service, tracker)
    pipeline_service = PipelineService(tracking_service, EventEngine({}))
    alert_engine = AlertEngine({})
    return pipeline_service, alert_engine


def _write_image(path: Path, fill: int) -> None:
    image = np.full((16, 16, 3), fill, dtype=np.uint8)
    cv2.imwrite(str(path), image)


def _make_synthetic_video(path: Path, num_frames: int) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (16, 16))
    for i in range(num_frames):
        writer.write(np.full((16, 16, 3), i * 20, dtype=np.uint8))
    writer.release()


class _OneFrameThenFailSource(BaseVideoSource):
    """Serves exactly one real frame, then raises on the next read() —
    isolates StreamManager._run()'s error-handling branches without
    depending on a real device/file failing on cue."""

    def __init__(self, camera_id: str, error: Exception) -> None:
        self._camera_id = camera_id
        self._error = error
        self._served = False
        self._open = False

    def open(self) -> None:
        self._open = True

    def read(self) -> Frame | None:
        if not self._served:
            self._served = True
            return Frame(
                camera_id=self._camera_id, image=np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0
            )
        raise self._error

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open


@pytest.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[object]:
    db_settings = DatabaseSettings(url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    engine = create_engine(db_settings)
    await init_models(engine)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


async def test_start_processes_real_frames_persists_and_broadcasts(
    tmp_path: object, session_factory: object
) -> None:
    images_dir = Path(str(tmp_path)) / "images"
    images_dir.mkdir()
    _write_image(images_dir / "a.jpg", 10)
    _write_image(images_dir / "b.jpg", 20)

    pipeline_service, alert_engine, alert_store = _build_real_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service, alert_engine, session_factory, broadcaster, PipelineSettings()
    )
    camera = Camera(
        id="cam-dir", name="Test", source_type=SourceType.DIRECTORY, uri=str(images_dir)
    )

    await manager.start(camera)
    try:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if manager.list_active()[0].frames_processed >= 2:
                break

        statuses = manager.list_active()
        assert len(statuses) == 1
        assert statuses[0].camera_id == "cam-dir"
        assert statuses[0].frames_processed >= 2
        assert statuses[0].last_error is None
    finally:
        await manager.stop("cam-dir")

    assert manager.list_active() == []
    assert len(alert_store.recent()) >= 1  # a person_detected alert really dispatched

    async with session_factory() as session:
        detections = await DetectionRepository(session).list()
        events = await EventRepository(session).list()
    assert len(detections) >= 2  # one per processed frame
    assert len(events) >= 1


async def _noop_session_factory() -> None:  # pragma: no cover - never called
    raise AssertionError("should not need a session for this test")


async def test_starting_an_already_active_camera_raises(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()

    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )
    camera = Camera(id="cam-x", name="Test", source_type=SourceType.DIRECTORY, uri=str(empty_dir))

    await manager.start(camera)
    try:
        with pytest.raises(ConfigurationError):
            await manager.start(camera)
    finally:
        await manager.stop("cam-x")


async def test_stopping_an_inactive_camera_raises() -> None:
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()

    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )

    with pytest.raises(ConfigurationError):
        await manager.stop("never-started")


async def test_stop_all_stops_every_active_stream(
    tmp_path: Path, session_factory: object
) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service, alert_engine, session_factory, broadcaster, PipelineSettings()
    )
    camera_a = Camera(id="cam-a", name="A", source_type=SourceType.DIRECTORY, uri=str(empty_dir))
    camera_b = Camera(id="cam-b", name="B", source_type=SourceType.DIRECTORY, uri=str(empty_dir))

    await manager.start(camera_a)
    await manager.start(camera_b)
    assert len(manager.list_active()) == 2

    await manager.stop_all()

    assert manager.list_active() == []


async def test_an_unsupported_source_type_fails_fast_without_starting_a_task(
    tmp_path: Path,
) -> None:
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()

    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )
    camera = Camera(
        id="cam-img", name="Still", source_type=SourceType.IMAGE, uri=str(tmp_path / "x.jpg")
    )

    with pytest.raises(ConfigurationError):
        await manager.start(camera)

    assert manager.list_active() == []


async def test_is_active_reflects_a_running_and_then_stopped_stream(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )
    camera = Camera(id="cam-active", name="T", source_type=SourceType.DIRECTORY, uri=str(empty_dir))

    assert manager.is_active("cam-active") is False
    await manager.start(camera)
    assert manager.is_active("cam-active") is True
    await manager.stop("cam-active")
    assert manager.is_active("cam-active") is False


async def test_a_finite_video_source_ends_the_stream_on_its_own(tmp_path: Path) -> None:
    """A real (non-directory) source that genuinely exhausts — proves the
    'source exhausted -> clean shutdown' path without needing an explicit
    stop() call, distinct from every other test which stops a stream that
    would otherwise poll forever."""
    video_path = tmp_path / "clip.mp4"
    _make_synthetic_video(video_path, num_frames=3)
    # No detections/events fired here — the point is to reach real source
    # exhaustion (frame is None -> break), not a persist-error shortcut.
    pipeline_service, alert_engine = _build_empty_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )
    camera = Camera(
        id="cam-file", name="File", source_type=SourceType.VIDEO_FILE, uri=str(video_path)
    )

    await manager.start(camera)
    for _ in range(100):
        await asyncio.sleep(0.05)
        if not manager.is_active("cam-file"):
            break

    assert manager.is_active("cam-file") is False
    assert manager.list_active() == []


async def test_frame_skip_processes_only_every_other_frame(
    tmp_path: Path, session_factory: object
) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for i, fill in enumerate([10, 20, 30, 40]):
        _write_image(images_dir / f"{i}.jpg", fill)
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service,
        alert_engine,
        session_factory,
        broadcaster,
        PipelineSettings(frame_skip=1),  # process 1 of every 2 frames
    )
    camera = Camera(
        id="cam-skip", name="Skip", source_type=SourceType.DIRECTORY, uri=str(images_dir)
    )

    await manager.start(camera)
    try:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if manager.list_active()[0].frames_processed >= 2:
                break
        await asyncio.sleep(0.1)  # let it settle; watch mode keeps polling an exhausted dir
        frames_processed = manager.list_active()[0].frames_processed
    finally:
        await manager.stop("cam-skip")

    assert frames_processed == 2  # 4 files in, every other one skipped


async def test_max_fps_throttles_between_processed_frames(
    tmp_path: Path, session_factory: object
) -> None:
    video_path = tmp_path / "clip.mp4"
    _make_synthetic_video(video_path, num_frames=3)
    pipeline_service, alert_engine, _ = _build_real_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service,
        alert_engine,
        session_factory,
        broadcaster,
        PipelineSettings(max_fps=20.0),  # 0.05s minimum between frames
    )
    camera = Camera(
        id="cam-fps", name="FPS", source_type=SourceType.VIDEO_FILE, uri=str(video_path)
    )

    started = time.monotonic()
    await manager.start(camera)
    for _ in range(100):
        await asyncio.sleep(0.02)
        if not manager.is_active("cam-fps"):
            break
    elapsed = time.monotonic() - started

    # 3 frames at >=0.05s apart is >=0.1s total; a real, if generous, floor
    # that would fail immediately if max_fps were silently ignored.
    assert elapsed >= 0.1


async def test_run_records_a_video_source_error_and_cleans_up() -> None:
    pipeline_service, alert_engine = _build_empty_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )
    camera = Camera(id="cam-err", name="Err", source_type=SourceType.DIRECTORY, uri="/unused")
    source = _OneFrameThenFailSource("cam-err", VideoSourceError("device disconnected"))
    status = StreamStatus(camera_id="cam-err", started_at=datetime.now(UTC))
    manager._statuses["cam-err"] = status  # noqa: SLF001 - seeding state _run() expects
    manager._sources["cam-err"] = source  # noqa: SLF001
    task = asyncio.create_task(manager._run(camera, source))  # noqa: SLF001
    manager._tasks["cam-err"] = task  # noqa: SLF001

    await task

    assert status.last_error == "device disconnected"
    assert "cam-err" not in manager._tasks  # noqa: SLF001
    assert "cam-err" not in manager._statuses  # noqa: SLF001
    assert "cam-err" not in manager._sources  # noqa: SLF001


async def test_run_records_an_unexpected_exception_and_cleans_up() -> None:
    pipeline_service, alert_engine = _build_empty_pipeline()
    broadcaster = StreamBroadcaster()
    manager = StreamManager(
        pipeline_service,
        alert_engine,
        _noop_session_factory,  # type: ignore[arg-type]
        broadcaster,
        PipelineSettings(),
    )
    camera = Camera(id="cam-boom", name="Boom", source_type=SourceType.DIRECTORY, uri="/unused")
    source = _OneFrameThenFailSource("cam-boom", RuntimeError("unexpected failure"))
    status = StreamStatus(camera_id="cam-boom", started_at=datetime.now(UTC))
    manager._statuses["cam-boom"] = status  # noqa: SLF001
    manager._sources["cam-boom"] = source  # noqa: SLF001
    task = asyncio.create_task(manager._run(camera, source))  # noqa: SLF001
    manager._tasks["cam-boom"] = task  # noqa: SLF001

    await task

    assert status.last_error == "unexpected failure"
    assert "cam-boom" not in manager._tasks  # noqa: SLF001
