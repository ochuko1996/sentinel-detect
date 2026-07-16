"""Smoke detector: requires a fine-tuned checkpoint, disabled by default.

No COCO class covers smoke. Activates once an operator supplies weights at
`models.weights_dir/smoke.pt` and sets `SENTINEL_DETECTORS__SMOKE__ENABLED=true`.
Many real-world fire/smoke datasets train one combined model — if that's
what you have, point both `fire` and `smoke` detectors' `model_key` at the
same weights file; ModelManager will share the one loaded instance.
"""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.interfaces.detector import detector_registry
from sentinel_detect.detectors.base import LabelMappedDetector


@detector_registry.register("smoke")
class SmokeDetector(LabelMappedDetector):
    detector_key = "smoke"
    label_map = {"smoke": DetectionClass.SMOKE}
