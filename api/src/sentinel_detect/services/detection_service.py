"""Detection engine orchestration: runs one frame through every active detector."""

from __future__ import annotations

from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.detector import BaseDetector


class DetectionService:
    """Fans a single frame out to every currently-active detector and merges results.

    "Active" detectors are whatever `detectors/factory.py` managed to build
    at startup — a detector configured as enabled but whose model failed to
    load simply isn't present here (see `build_enabled_detectors`).
    """

    def __init__(self, detectors: dict[str, BaseDetector]) -> None:
        self._detectors = detectors

    def detect(self, frame: Frame) -> list[Detection]:
        detections: list[Detection] = []
        for detector in self._detectors.values():
            detections.extend(detector.detect(frame))
        return detections

    def active_detector_keys(self) -> list[str]:
        return sorted(self._detectors)
