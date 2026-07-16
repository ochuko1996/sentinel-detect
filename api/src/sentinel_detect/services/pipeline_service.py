"""Full per-frame pipeline: detection -> tracking -> event rules.

This is the composition point the spec's "Detection Pipeline" diagram
describes (input -> preprocessing -> inference -> post-processing ->
tracking -> event detection -> alert generation -> storage -> ...); storage
is Phase 6's job (the caller persists what this returns — see
`api/routers/detect.py`), alert generation is Phase 5's `AlertEngine`.
"""

from __future__ import annotations

from sentinel_detect.core.entities.camera import Region
from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.core.interfaces.event_rule import EventContext
from sentinel_detect.services.event_engine import EventEngine
from sentinel_detect.services.tracking_service import TrackingService


class PipelineService:
    def __init__(self, tracking_service: TrackingService, event_engine: EventEngine) -> None:
        self._tracking_service = tracking_service
        self._event_engine = event_engine

    def process_frame(
        self, frame: Frame, regions: tuple[Region, ...] = ()
    ) -> tuple[list[Detection], list[TrackedObject], list[Event]]:
        detections, tracked_objects = self._tracking_service.process_frame(frame)
        context = EventContext(
            camera_id=frame.camera_id,
            tracked_objects=tuple(tracked_objects),
            regions=regions,
            timestamp=frame.timestamp,
        )
        events = self._event_engine.evaluate(context)
        return detections, tracked_objects, events

    def reset(self, camera_id: str) -> None:
        self._tracking_service.reset(camera_id)

    def active_detector_keys(self) -> list[str]:
        return self._tracking_service.active_detector_keys()

    def active_rule_keys(self) -> list[str]:
        return self._event_engine.active_rule_keys()
