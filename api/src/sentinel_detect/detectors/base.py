"""Shared implementation for every built-in detector.

Every detector's job reduces to the same three steps: filter an inference
backend's raw predictions to the classes this detector owns, apply this
detector's confidence threshold, and map the backend's native class name to
a `DetectionClass`. `LabelMappedDetector` implements that once; concrete
detectors (person/vehicle/weapon/fire/smoke/ppe/animal) just declare a
`label_map`.

Class-name matching is case/separator-insensitive because custom-trained
weapon/fire/smoke/PPE checkpoints in the wild use inconsistent naming
conventions (`"Hard-Hat"`, `"hard_hat"`, `"helmet"`, ...) — an exact-match-only
map would silently detect nothing against a differently-named dataset.
"""

from __future__ import annotations

from functools import cache
from typing import ClassVar

from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.detector import BaseDetector


def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


class LabelMappedDetector(BaseDetector):
    """Concrete detectors set `detector_key` and `label_map` and inherit `detect`."""

    detector_key: ClassVar[str]
    label_map: ClassVar[dict[str, DetectionClass]]
    """Maps the inference backend's native class name to this detector's DetectionClass."""

    def detect(self, frame: Frame) -> list[Detection]:
        raw_predictions = self.model.predict(frame)
        names = self.model.class_names
        normalized_map = self._normalized_label_map()

        detections: list[Detection] = []
        for raw in raw_predictions:
            if raw.confidence < self.confidence_threshold:
                continue
            raw_name = names.get(raw.class_id)
            if raw_name is None:
                continue
            label = normalized_map.get(_normalize(raw_name))
            if label is None:
                continue
            detections.append(
                Detection(
                    camera_id=frame.camera_id,
                    detector=self.detector_key,
                    label=label,
                    confidence=raw.confidence,
                    bbox=raw.bbox,
                    frame_width=frame.width,
                    frame_height=frame.height,
                    timestamp=frame.timestamp,
                )
            )
        return detections

    @classmethod
    @cache
    def _normalized_label_map(cls) -> dict[str, DetectionClass]:
        return {_normalize(name): label for name, label in cls.label_map.items()}
