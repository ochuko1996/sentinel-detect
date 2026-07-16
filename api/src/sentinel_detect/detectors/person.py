"""Person detector: runs on the stock COCO checkpoint, enabled by default."""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("person")
class PersonDetector(LabelMappedDetector):
    detector_key = "person"
    label_map = {"person": DetectionClass.PERSON}
