"""Detection + tracking orchestration: assigns persistent identities to detections."""

from __future__ import annotations

from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.core.interfaces.tracker import BaseTracker
from sentinel_detect.services.detection_service import DetectionService


class TrackingService:
    def __init__(self, detection_service: DetectionService, tracker: BaseTracker) -> None:
        self._detection_service = detection_service
        self._tracker = tracker

    def process_frame(self, frame: Frame) -> tuple[list[Detection], list[TrackedObject]]:
        detections = self._detection_service.detect(frame)
        tracked_objects = self._tracker.update(frame.camera_id, detections)
        return detections, tracked_objects

    def reset(self, camera_id: str) -> None:
        """Discard tracking state for `camera_id`.

        Callers processing a one-shot video upload (as opposed to a
        persistent camera stream) must call this once done, or the tracker
        accumulates per-`camera_id` state forever for every ephemeral upload.
        """
        self._tracker.reset(camera_id)

    def active_detector_keys(self) -> list[str]:
        return self._detection_service.active_detector_keys()
