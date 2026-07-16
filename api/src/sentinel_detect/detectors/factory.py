"""Composition helper: turns enabled-detector config into live BaseDetector instances."""

from __future__ import annotations

from sentinel_detect.config.settings import AppSettings
from sentinel_detect.core.exceptions import ConfigurationError, ModelLoadError
from sentinel_detect.core.interfaces.detector import BaseDetector, detector_registry
from sentinel_detect.models.manager import ModelManager
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)


def build_enabled_detectors(
    settings: AppSettings, model_manager: ModelManager
) -> dict[str, BaseDetector]:
    """Instantiate every enabled, successfully-loadable detector.

    A detector whose model fails to load (typically: enabled but its custom
    weights file is absent, or the 'vision' extra isn't installed) is logged
    and skipped rather than crashing startup, so e.g. person/vehicle/animal
    keep working even if weapon weights haven't been supplied yet.
    """
    detectors: dict[str, BaseDetector] = {}
    for key in settings.enabled_detector_keys():
        detector_cfg = settings.detectors[key]
        try:
            model = model_manager.get(detector_cfg.model_key)
        except (ModelLoadError, ConfigurationError) as exc:
            logger.error(
                "detector_unavailable",
                detector=key,
                model_key=detector_cfg.model_key,
                reason=str(exc),
            )
            continue

        detector_cls = detector_registry.get(key)
        detectors[key] = detector_cls(
            model,
            confidence_threshold=detector_cfg.confidence_threshold,
            iou_threshold=detector_cfg.iou_threshold,
        )
    return detectors
