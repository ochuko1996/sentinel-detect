"""Vehicle detector: runs on the stock COCO checkpoint, enabled by default."""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("vehicle")
class VehicleDetector(LabelMappedDetector):
    detector_key = "vehicle"
    label_map = {
        "car": DetectionClass.CAR,
        "bus": DetectionClass.BUS,
        "truck": DetectionClass.TRUCK,
        "motorcycle": DetectionClass.MOTORCYCLE,
        "bicycle": DetectionClass.BICYCLE,
    }
