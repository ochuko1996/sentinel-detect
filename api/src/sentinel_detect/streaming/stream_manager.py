"""Manages live per-camera streaming tasks.

Runs the exact same detection -> tracking -> event -> alert -> storage
pipeline `POST /detect/video` uses for uploaded files, just against an
indefinitely-running background `asyncio.Task` per camera instead of a
bounded upload — reusing `PipelineService`/`AlertEngine`/the repositories,
not a parallel implementation.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sentinel_detect.config.settings import PipelineSettings
from sentinel_detect.core.entities.camera import Camera
from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.exceptions import ConfigurationError, VideoSourceError
from sentinel_detect.core.interfaces.video_source import BaseVideoSource
from sentinel_detect.database.repositories import (
    AlertRepository,
    DetectionRepository,
    EventRepository,
)
from sentinel_detect.services.alert_engine import AlertEngine
from sentinel_detect.services.pipeline_service import PipelineService
from sentinel_detect.streaming.broadcaster import StreamBroadcaster
from sentinel_detect.streaming.factory import build_video_source
from sentinel_detect.utils.logging import get_logger
from sentinel_detect.utils.metrics import ALERTS_TOTAL, DETECTIONS_TOTAL, EVENTS_TOTAL

logger = get_logger(__name__)


@dataclass
class StreamStatus:
    camera_id: str
    started_at: datetime
    frames_processed: int = 0
    last_error: str | None = None


class StreamManager:
    def __init__(
        self,
        pipeline_service: PipelineService,
        alert_engine: AlertEngine,
        session_factory: async_sessionmaker[AsyncSession],
        broadcaster: StreamBroadcaster,
        pipeline_settings: PipelineSettings,
    ) -> None:
        self._pipeline_service = pipeline_service
        self._alert_engine = alert_engine
        self._session_factory = session_factory
        self._broadcaster = broadcaster
        self._pipeline_settings = pipeline_settings
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._statuses: dict[str, StreamStatus] = {}
        self._sources: dict[str, BaseVideoSource] = {}

    def is_active(self, camera_id: str) -> bool:
        return camera_id in self._tasks

    def list_active(self) -> list[StreamStatus]:
        return list(self._statuses.values())

    async def start(self, camera: Camera) -> None:
        if camera.id in self._tasks:
            raise ConfigurationError(f"camera '{camera.id}' is already streaming")

        source = build_video_source(camera)  # raises ConfigurationError for unsupported types
        self._statuses[camera.id] = StreamStatus(camera_id=camera.id, started_at=datetime.now(UTC))
        self._sources[camera.id] = source
        self._tasks[camera.id] = asyncio.create_task(self._run(camera, source))

    async def stop(self, camera_id: str) -> None:
        task = self._tasks.pop(camera_id, None)
        if task is None:
            raise ConfigurationError(f"camera '{camera_id}' is not streaming")
        # `read()` runs on a worker thread and may currently be blocked
        # there; `task.cancel()` alone can't interrupt it (cancellation only
        # takes effect once the thread's call returns). Close the source
        # first so an interruptible implementation (e.g. DirectoryVideoSource
        # waiting on a poll interval) wakes up and returns promptly.
        source = self._sources.pop(camera_id, None)
        if source is not None:
            source.close()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._statuses.pop(camera_id, None)

    async def stop_all(self) -> None:
        for camera_id in list(self._tasks):
            await self.stop(camera_id)

    async def _run(self, camera: Camera, source: BaseVideoSource) -> None:
        status = self._statuses[camera.id]
        frame_skip = self._pipeline_settings.frame_skip
        frame_interval = (
            1.0 / self._pipeline_settings.max_fps if self._pipeline_settings.max_fps else None
        )
        skip_counter = 0

        try:
            source.open()
            while True:
                frame = await asyncio.to_thread(source.read)
                if frame is None:
                    break  # source exhausted (batch directory mode, or a finite file ended)

                if skip_counter < frame_skip:
                    skip_counter += 1
                    continue
                skip_counter = 0

                detections, tracked_objects, events = self._pipeline_service.process_frame(
                    frame, camera.regions
                )
                status.frames_processed += 1

                await self._broadcaster.broadcast(
                    camera.id,
                    {
                        "frame_index": frame.frame_index,
                        "timestamp": frame.timestamp.isoformat(),
                        "tracks": [
                            {
                                "track_id": t.track_id,
                                "label": t.label.value,
                                "confidence": t.confidence,
                                "bbox": {
                                    "x1": t.bbox.x1,
                                    "y1": t.bbox.y1,
                                    "x2": t.bbox.x2,
                                    "y2": t.bbox.y2,
                                },
                            }
                            for t in tracked_objects
                        ],
                    },
                )

                if detections or events:
                    await self._persist(camera.id, detections, events)

                if frame_interval is not None:
                    await asyncio.sleep(frame_interval)
        except asyncio.CancelledError:
            raise
        except VideoSourceError as exc:
            status.last_error = str(exc)
            logger.error("stream_failed", camera_id=camera.id, error=str(exc))
        except Exception as exc:
            status.last_error = str(exc)
            logger.error("stream_failed", camera_id=camera.id, error=str(exc), exc_info=True)
        finally:
            source.close()
            self._pipeline_service.reset(camera.id)
            self._tasks.pop(camera.id, None)
            self._statuses.pop(camera.id, None)
            self._sources.pop(camera.id, None)

    async def _persist(
        self, camera_id: str, detections: list[Detection], events: list[Event]
    ) -> None:
        async with self._session_factory() as session:
            detection_repo = DetectionRepository(session)
            for detection in detections:
                await detection_repo.create(detection)
                DETECTIONS_TOTAL.labels(detector=detection.detector).inc()

            if events:
                alerts = await self._alert_engine.dispatch(events)
                event_repo = EventRepository(session)
                alert_repo = AlertRepository(session)
                for event in events:
                    await event_repo.create(event)
                    EVENTS_TOTAL.labels(rule=event.rule).inc()
                for alert in alerts:
                    await alert_repo.create(alert)
                    ALERTS_TOTAL.labels(
                        channel=alert.channel.value, status=alert.status.value
                    ).inc()

            await session.commit()

        logger.info(
            "stream_frame_persisted",
            camera_id=camera_id,
            detection_count=len(detections),
            event_count=len(events),
        )
