"""Inference backend port.

`BaseInferenceModel` abstracts over the specific model architecture/runtime
(Ultralytics YOLO today; RT-DETR, ONNX Runtime, or TensorRT later) so that
detectors (core/interfaces/detector.py) never depend on a concrete backend.
A single loaded model instance can be shared by multiple detectors (e.g. one
COCO-pretrained model backs both the person and vehicle detectors).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame


@dataclass(slots=True, frozen=True)
class RawPrediction:
    """One unfiltered, un-mapped box as produced directly by an inference backend.

    `class_id` is the backend/model's native class index; detectors are
    responsible for mapping it to a `DetectionClass` and applying confidence
    thresholds — `BaseInferenceModel` implementations must not know about the
    SENTINEL Detect class taxonomy.
    """

    bbox: BoundingBox
    class_id: int
    confidence: float


class BaseInferenceModel(ABC):
    """Port for a loaded object-detection model backend."""

    @abstractmethod
    def load(self) -> None:
        """Load weights and prepare the backend for inference (idempotent)."""

    @abstractmethod
    def predict(self, frame: Frame) -> list[RawPrediction]:
        """Run a forward pass on `frame` and return raw, unfiltered predictions."""

    @abstractmethod
    def warmup(self) -> None:
        """Run a dummy inference to pay JIT/CUDA warm-up cost outside the request path."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Whether `load()` has completed successfully."""

    @property
    @abstractmethod
    def class_names(self) -> dict[int, str]:
        """Map of this backend's native class index to its native class name.

        Detectors use this to resolve `RawPrediction.class_id` before mapping
        the name into a `DetectionClass`. Raises if called before `load()`.
        """
