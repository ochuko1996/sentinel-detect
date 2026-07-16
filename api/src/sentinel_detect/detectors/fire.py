"""Fire detector: requires a fine-tuned checkpoint, disabled by default.

No COCO class covers fire/flames. Activates once an operator supplies
weights at `models.weights_dir/fire.pt` and sets
`SENTINEL_DETECTORS__FIRE__ENABLED=true`.
"""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("fire")
class FireDetector(LabelMappedDetector):
    detector_key = "fire"
    label_map = {
        "fire": DetectionClass.FIRE,
        "flame": DetectionClass.FLAME,
        "flames": DetectionClass.FLAME,
    }
