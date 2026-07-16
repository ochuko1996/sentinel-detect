import numpy as np
import pytest

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.model import BaseInferenceModel, RawPrediction
from sentinel_detect.detectors.animal import AnimalDetector
from sentinel_detect.detectors.person import PersonDetector
from sentinel_detect.detectors.ppe import PPEDetector
from sentinel_detect.detectors.vehicle import VehicleDetector
from sentinel_detect.detectors.weapon import WeaponDetector


class FakeModel(BaseInferenceModel):
    """A BaseInferenceModel stand-in with canned predictions, for testing
    detector label-mapping/threshold logic without real inference."""

    def __init__(self, names: dict[int, str], predictions: list[RawPrediction]) -> None:
        self._names = names
        self._predictions = predictions

    def load(self) -> None:
        pass

    def predict(self, frame: Frame) -> list[RawPrediction]:
        return self._predictions

    def warmup(self) -> None:
        pass

    @property
    def is_loaded(self) -> bool:
        return True

    @property
    def class_names(self) -> dict[int, str]:
        return self._names


def _frame() -> Frame:
    return Frame(camera_id="cam-1", image=np.zeros((10, 10, 3), dtype=np.uint8), frame_index=0)


def _box() -> BoundingBox:
    return BoundingBox(x1=0, y1=0, x2=5, y2=5)


def test_person_detector_maps_person_class_and_applies_confidence_threshold() -> None:
    model = FakeModel(
        names={0: "person", 1: "bicycle"},
        predictions=[
            RawPrediction(bbox=_box(), class_id=0, confidence=0.9),
            RawPrediction(bbox=_box(), class_id=0, confidence=0.1),  # below threshold
            RawPrediction(bbox=_box(), class_id=1, confidence=0.9),  # not this detector's class
        ],
    )
    detector = PersonDetector(model, confidence_threshold=0.5, iou_threshold=0.45)

    detections = detector.detect(_frame())

    assert len(detections) == 1
    assert detections[0].label is DetectionClass.PERSON
    assert detections[0].detector == "person"
    assert detections[0].confidence == 0.9


def test_vehicle_detector_maps_every_coco_vehicle_class() -> None:
    model = FakeModel(
        names={2: "car", 5: "bus", 7: "truck", 3: "motorcycle", 1: "bicycle", 0: "person"},
        predictions=[
            RawPrediction(bbox=_box(), class_id=cid, confidence=0.9)
            for cid in (2, 5, 7, 3, 1, 0)
        ],
    )
    detector = VehicleDetector(model, confidence_threshold=0.5, iou_threshold=0.45)

    labels = {d.label for d in detector.detect(_frame())}

    assert labels == {
        DetectionClass.CAR,
        DetectionClass.BUS,
        DetectionClass.TRUCK,
        DetectionClass.MOTORCYCLE,
        DetectionClass.BICYCLE,
    }


def test_animal_detector_ignores_classes_outside_its_label_map() -> None:
    model = FakeModel(
        names={16: "dog", 17: "horse", 0: "person"},
        predictions=[
            RawPrediction(bbox=_box(), class_id=16, confidence=0.9),
            RawPrediction(bbox=_box(), class_id=17, confidence=0.9),
            RawPrediction(bbox=_box(), class_id=0, confidence=0.9),
        ],
    )
    detector = AnimalDetector(model, confidence_threshold=0.5, iou_threshold=0.45)

    labels = {d.label for d in detector.detect(_frame())}

    assert labels == {DetectionClass.DOG, DetectionClass.HORSE}


def test_weapon_detector_maps_gun_synonyms() -> None:
    model = FakeModel(
        names={0: "pistol", 1: "handgun", 2: "rifle"},
        predictions=[
            RawPrediction(bbox=_box(), class_id=0, confidence=0.9),
            RawPrediction(bbox=_box(), class_id=1, confidence=0.9),
            RawPrediction(bbox=_box(), class_id=2, confidence=0.9),
        ],
    )
    detector = WeaponDetector(model, confidence_threshold=0.5, iou_threshold=0.45)

    labels = [d.label for d in detector.detect(_frame())]

    assert labels == [DetectionClass.GUN, DetectionClass.GUN, DetectionClass.RIFLE]


@pytest.mark.parametrize("raw_name", ["Hard-Hat", "hard_hat", "HARDHAT", "helmet"])
def test_label_matching_is_case_and_separator_insensitive(raw_name: str) -> None:
    model = FakeModel(
        names={0: raw_name},
        predictions=[RawPrediction(bbox=_box(), class_id=0, confidence=0.9)],
    )
    detector = PPEDetector(model, confidence_threshold=0.5, iou_threshold=0.45)

    detections = detector.detect(_frame())

    assert len(detections) == 1
    assert detections[0].label is DetectionClass.HARD_HAT


def test_unresolvable_class_id_is_skipped_not_raised() -> None:
    model = FakeModel(
        names={0: "person"},
        predictions=[RawPrediction(bbox=_box(), class_id=999, confidence=0.9)],
    )
    detector = PersonDetector(model, confidence_threshold=0.5, iou_threshold=0.45)

    assert detector.detect(_frame()) == []
