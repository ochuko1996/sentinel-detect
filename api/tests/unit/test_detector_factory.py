import numpy as np

from sentinel_detect.config.settings import AppSettings
from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.exceptions import ModelLoadError
from sentinel_detect.core.interfaces.model import BaseInferenceModel, RawPrediction
from sentinel_detect.detectors import build_enabled_detectors
from sentinel_detect.models.manager import ModelManager


def _frame() -> Frame:
    return Frame(camera_id="cam-1", image=np.zeros((4, 4, 3), dtype=np.uint8), frame_index=0)


class _EmptyFakeModel(BaseInferenceModel):
    """Loads successfully but never detects anything."""

    def load(self) -> None:
        pass

    def predict(self, frame: Frame) -> list[RawPrediction]:
        return []

    def warmup(self) -> None:
        pass

    @property
    def is_loaded(self) -> bool:
        return True

    @property
    def class_names(self) -> dict[int, str]:
        return {}


class _OnePersonFakeModel(BaseInferenceModel):
    """Always reports one confident 'person' detection."""

    def load(self) -> None:
        pass

    def predict(self, frame: Frame) -> list[RawPrediction]:
        return [RawPrediction(bbox=BoundingBox(x1=0, y1=0, x2=2, y2=2), class_id=0, confidence=0.9)]

    def warmup(self) -> None:
        pass

    @property
    def is_loaded(self) -> bool:
        return True

    @property
    def class_names(self) -> dict[int, str]:
        return {0: "person"}


class _AlwaysFailsManager(ModelManager):
    def get(self, model_key: str) -> BaseInferenceModel:
        raise ModelLoadError(f"no weights for {model_key}")


class _AlwaysSucceedsManager(ModelManager):
    def get(self, model_key: str) -> BaseInferenceModel:
        return _EmptyFakeModel()


class _PartialManager(ModelManager):
    """Fails only for the weapon model_key; succeeds for everything else."""

    def get(self, model_key: str) -> BaseInferenceModel:
        if model_key == "yolov11n_weapon":
            raise ModelLoadError("weapon.pt not found")
        return _EmptyFakeModel()


class _OnePersonManager(ModelManager):
    def get(self, model_key: str) -> BaseInferenceModel:
        return _OnePersonFakeModel()


def test_build_enabled_detectors_skips_detectors_whose_model_fails_to_load() -> None:
    settings = AppSettings(_env_file=None)
    manager = _AlwaysFailsManager(settings.models)

    detectors = build_enabled_detectors(settings, manager)

    assert detectors == {}


def test_build_enabled_detectors_builds_one_instance_per_enabled_key() -> None:
    settings = AppSettings(_env_file=None)
    manager = _AlwaysSucceedsManager(settings.models)

    detectors = build_enabled_detectors(settings, manager)

    assert set(detectors) == set(settings.enabled_detector_keys())
    for detector in detectors.values():
        assert detector.detect(_frame()) == []


def test_a_partially_available_detector_set_still_builds_the_rest() -> None:
    settings = AppSettings(_env_file=None)
    settings.detectors["weapon"].enabled = True  # force-enable a detector with no real weights

    detectors = build_enabled_detectors(settings, _PartialManager(settings.models))

    assert "weapon" not in detectors
    assert {"person", "vehicle", "animal"} <= set(detectors)


def test_detections_from_a_built_detector_are_real_detection_objects() -> None:
    settings = AppSettings(_env_file=None)
    detectors = build_enabled_detectors(settings, _OnePersonManager(settings.models))

    detections = detectors["person"].detect(_frame())

    assert len(detections) == 1
    assert isinstance(detections[0], Detection)
    assert detections[0].label.value == "person"
