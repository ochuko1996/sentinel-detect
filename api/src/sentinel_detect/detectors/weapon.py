"""Weapon detector: requires a fine-tuned checkpoint, disabled by default.

No open pretrained COCO model covers guns or rifles. COCO does have a
'knife' class, but it's tuned for kitchenware/cutlery imagery, not security
framing, so it isn't a substitute for a real weapon-detection model. This
detector activates once an operator supplies weights at
`models.weights_dir/weapon.pt` (or repoints `model_key`) and sets
`SENTINEL_DETECTORS__WEAPON__ENABLED=true`.
"""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("weapon")
class WeaponDetector(LabelMappedDetector):
    detector_key = "weapon"
    label_map = {
        "gun": DetectionClass.GUN,
        "pistol": DetectionClass.GUN,
        "handgun": DetectionClass.GUN,
        "rifle": DetectionClass.RIFLE,
        "knife": DetectionClass.KNIFE,
    }
