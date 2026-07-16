"""Lazy, cached construction of inference model instances by `model_key`.

Detectors that share a `model_key` (e.g. person/vehicle/animal all default
to 'yolov11n') share the same `BaseInferenceModel` instance, so weights are
loaded into memory/GPU once regardless of how many detectors use them.
"""

from __future__ import annotations

from sentinel_detect.config.settings import ModelSettings
from sentinel_detect.core.exceptions import ConfigurationError
from sentinel_detect.core.interfaces.model import BaseInferenceModel
from sentinel_detect.models.caching import CachingInferenceModel
from sentinel_detect.models.yolo import UltralyticsYoloModel


class ModelManager:
    """Resolves a `model_key` to a loaded, process-wide-shared `BaseInferenceModel`."""

    def __init__(self, settings: ModelSettings) -> None:
        self._settings = settings
        self._instances: dict[str, BaseInferenceModel] = {}

    def get(self, model_key: str) -> BaseInferenceModel:
        if model_key not in self._instances:
            self._instances[model_key] = self._build(model_key)
        return self._instances[model_key]

    def loaded_models(self) -> dict[str, BaseInferenceModel]:
        """Every model instance successfully built so far, keyed by `model_key`."""
        return dict(self._instances)

    def _build(self, model_key: str) -> BaseInferenceModel:
        try:
            weights_filename = self._settings.weights[model_key]
        except KeyError as exc:
            raise ConfigurationError(
                f"no weights filename configured for model_key '{model_key}'; "
                f"set it under SENTINEL_MODELS__WEIGHTS__{model_key.upper()}"
            ) from exc

        model = UltralyticsYoloModel(
            weights_path=self._settings.weights_dir / weights_filename,
            device=self._settings.device,
            inference_size=self._settings.default_inference_size,
        )
        model.load()
        # Wrapped so detectors sharing this model_key (e.g. person/vehicle/
        # animal all on 'yolov11n') don't each run their own forward pass
        # over the same frame — see CachingInferenceModel.
        return CachingInferenceModel(model)
