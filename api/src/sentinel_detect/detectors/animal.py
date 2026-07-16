"""Animal detector: runs on the stock COCO checkpoint, enabled by default.

COCO's 80 classes include dog/cat/cow/horse but have no 'goat' class — goat
detection requires pointing this detector at a custom-trained model_key via
config (`SENTINEL_DETECTORS__ANIMAL__MODEL_KEY`).
"""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("animal")
class AnimalDetector(LabelMappedDetector):
    detector_key = "animal"
    label_map = {
        "dog": DetectionClass.DOG,
        "cat": DetectionClass.CAT,
        "cow": DetectionClass.COW,
        "horse": DetectionClass.HORSE,
    }
