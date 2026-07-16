"""Detector port and the shared plugin registry detector modules register into.

A detector is the boundary between a raw inference backend and the domain
taxonomy: it owns the mapping from a model's native class indices to
`DetectionClass` values, and the confidence/IoU thresholds for its own
concern (person, vehicle, weapon, ...). This is what lets several detectors
share one underlying model, and lets a new detector module be added by
registering a new key — no core code changes required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.model import BaseInferenceModel
from sentinel_detect.core.registry import Registry


class BaseDetector(ABC):
    """Port for a single detection module (person, vehicle, weapon, ...)."""

    def __init__(
        self, model: BaseInferenceModel, *, confidence_threshold: float, iou_threshold: float
    ) -> None:
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold

    @abstractmethod
    def detect(self, frame: Frame) -> list[Detection]:
        """Run inference on `frame` and return this detector's Detection objects."""


detector_registry: Registry[BaseDetector] = Registry("detector")
