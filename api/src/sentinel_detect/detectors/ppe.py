"""PPE detector: requires a fine-tuned checkpoint, disabled by default.

No COCO class covers hard hats, safety vests, gloves, or safety glasses.
Activates once an operator supplies weights at `models.weights_dir/ppe.pt`
and sets `SENTINEL_DETECTORS__PPE__ENABLED=true`. The label_map includes
common alternate names used by public PPE-detection datasets (e.g.
Roboflow's "helmet"/"vest"/"goggles") since class-name conventions vary
by training set.
"""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("ppe")
class PPEDetector(LabelMappedDetector):
    detector_key = "ppe"
    label_map = {
        "hard_hat": DetectionClass.HARD_HAT,
        "hardhat": DetectionClass.HARD_HAT,
        "helmet": DetectionClass.HARD_HAT,
        "safety_vest": DetectionClass.SAFETY_VEST,
        "vest": DetectionClass.SAFETY_VEST,
        "gloves": DetectionClass.GLOVES,
        "glove": DetectionClass.GLOVES,
        "safety_glasses": DetectionClass.SAFETY_GLASSES,
        "goggles": DetectionClass.SAFETY_GLASSES,
    }
