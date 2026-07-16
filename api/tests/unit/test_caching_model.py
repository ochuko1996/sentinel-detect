"""Tests for CachingInferenceModel: the Phase 9 fix for detectors that share
a model_key each running their own redundant forward pass over one frame."""

from __future__ import annotations

import numpy as np

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.model import BaseInferenceModel, RawPrediction
from sentinel_detect.detectors.person import PersonDetector
from sentinel_detect.detectors.vehicle import VehicleDetector
from sentinel_detect.models.caching import CachingInferenceModel
from sentinel_detect.services.detection_service import DetectionService


class _CountingModel(BaseInferenceModel):
    """A BaseInferenceModel stand-in that counts real predict() calls."""

    def __init__(self, names: dict[int, str], predictions: list[RawPrediction]) -> None:
        self._names = names
        self._predictions = predictions
        self.load_calls = 0
        self.predict_calls = 0
        self.warmup_calls = 0

    def load(self) -> None:
        self.load_calls += 1

    def predict(self, frame: Frame) -> list[RawPrediction]:
        self.predict_calls += 1
        return self._predictions

    def warmup(self) -> None:
        self.warmup_calls += 1

    @property
    def is_loaded(self) -> bool:
        return True

    @property
    def class_names(self) -> dict[int, str]:
        return self._names


def _frame(frame_index: int = 0) -> Frame:
    return Frame(
        camera_id="cam-1", image=np.zeros((10, 10, 3), dtype=np.uint8), frame_index=frame_index
    )


def test_repeat_predict_on_the_same_frame_object_hits_the_wrapped_model_once() -> None:
    wrapped = _CountingModel(names={}, predictions=[])
    model = CachingInferenceModel(wrapped)
    frame = _frame()

    model.predict(frame)
    model.predict(frame)
    model.predict(frame)

    assert wrapped.predict_calls == 1


def test_predict_on_a_different_frame_object_runs_inference_again() -> None:
    wrapped = _CountingModel(names={}, predictions=[])
    model = CachingInferenceModel(wrapped)
    # Both kept alive simultaneously so CPython can't reuse frame_a's
    # address for frame_b once frame_a's refcount drops — the real pipeline
    # always holds a frame's reference for the duration it's used across
    # detectors, so that hazard doesn't arise there, but a same-address
    # false positive here would prove nothing about identity-based caching.
    frame_a = _frame()
    frame_b = _frame()  # a distinct Frame object, even with identical content

    model.predict(frame_a)
    model.predict(frame_b)

    assert wrapped.predict_calls == 2


def test_cached_result_is_returned_unchanged() -> None:
    box = BoundingBox(x1=0, y1=0, x2=5, y2=5)
    predictions = [RawPrediction(bbox=box, class_id=0, confidence=0.9)]
    wrapped = _CountingModel(names={0: "person"}, predictions=predictions)
    model = CachingInferenceModel(wrapped)
    frame = _frame()

    first = model.predict(frame)
    second = model.predict(frame)

    assert first == predictions
    assert second == predictions


def test_load_warmup_is_loaded_and_class_names_delegate_to_the_wrapped_model() -> None:
    wrapped = _CountingModel(names={0: "person"}, predictions=[])
    model = CachingInferenceModel(wrapped)

    model.load()
    model.warmup()

    assert wrapped.load_calls == 1
    assert wrapped.warmup_calls == 1
    assert model.is_loaded is True
    assert model.class_names == {0: "person"}


def test_detectors_sharing_a_caching_model_only_trigger_one_real_inference_per_frame() -> None:
    wrapped = _CountingModel(
        names={0: "person", 2: "car"},
        predictions=[
            RawPrediction(bbox=BoundingBox(x1=0, y1=0, x2=5, y2=5), class_id=0, confidence=0.9),
            RawPrediction(bbox=BoundingBox(x1=0, y1=0, x2=5, y2=5), class_id=2, confidence=0.9),
        ],
    )
    shared_model = CachingInferenceModel(wrapped)
    person_detector = PersonDetector(shared_model, confidence_threshold=0.5, iou_threshold=0.45)
    vehicle_detector = VehicleDetector(shared_model, confidence_threshold=0.5, iou_threshold=0.45)
    service = DetectionService({"person": person_detector, "vehicle": vehicle_detector})

    detections = service.detect(_frame())

    assert wrapped.predict_calls == 1
    labels = {d.label for d in detections}
    assert labels == {DetectionClass.PERSON, DetectionClass.CAR}
