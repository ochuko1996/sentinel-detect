from sentinel_detect.config.settings import TrackingSettings
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.tracking.byte_track import ByteTracker

CAMERA = "cam-1"


def _settings(**overrides: object) -> TrackingSettings:
    defaults: dict[str, object] = {
        "min_hits": 2,
        "max_age": 2,
        "iou_threshold": 0.3,
        "second_stage_iou_threshold": 0.2,
        "high_confidence_threshold": 0.6,
    }
    defaults.update(overrides)
    return TrackingSettings(**defaults)  # type: ignore[arg-type]


def _det(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    confidence: float = 0.9,
    label: DetectionClass = DetectionClass.PERSON,
) -> Detection:
    return Detection(
        camera_id=CAMERA,
        detector=label.value,
        label=label,
        confidence=confidence,
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        frame_width=640,
        frame_height=480,
    )


def test_new_track_is_not_emitted_until_min_hits_reached() -> None:
    tracker = ByteTracker(_settings(min_hits=2))

    first = tracker.update(CAMERA, [_det(0, 0, 20, 20)])
    assert first == []

    second = tracker.update(CAMERA, [_det(1, 1, 21, 21)])
    assert len(second) == 1
    assert second[0].hits == 2


def test_smoothly_moving_object_keeps_the_same_track_id() -> None:
    tracker = ByteTracker(_settings(min_hits=1))

    ids: list[int] = []
    for step in range(5):
        dx = step * 3  # small overlapping movement each frame
        result = tracker.update(CAMERA, [_det(dx, 0, dx + 20, 20)])
        ids.append(result[0].track_id)

    assert len(set(ids)) == 1


def test_track_is_removed_after_max_age_and_reappearance_gets_a_new_id() -> None:
    tracker = ByteTracker(_settings(min_hits=1, max_age=2))

    first = tracker.update(CAMERA, [_det(0, 0, 20, 20)])
    original_id = first[0].track_id

    # No detections for more than max_age frames: the track should be dropped.
    tracker.update(CAMERA, [])
    tracker.update(CAMERA, [])
    tracker.update(CAMERA, [])

    reappeared = tracker.update(CAMERA, [_det(200, 200, 220, 220)])

    assert reappeared[0].track_id != original_id


def test_different_labels_are_tracked_independently_even_with_overlapping_boxes() -> None:
    tracker = ByteTracker(_settings(min_hits=1))

    result = tracker.update(
        CAMERA,
        [
            _det(0, 0, 20, 20, label=DetectionClass.PERSON),
            _det(0, 0, 20, 20, label=DetectionClass.CAR),
        ],
    )

    assert len(result) == 2
    ids_by_label = {r.label: r.track_id for r in result}
    assert ids_by_label[DetectionClass.PERSON] != ids_by_label[DetectionClass.CAR]

    # Confirm they stay separate on a second frame too.
    result2 = tracker.update(
        CAMERA,
        [
            _det(1, 1, 21, 21, label=DetectionClass.PERSON),
            _det(1, 1, 21, 21, label=DetectionClass.CAR),
        ],
    )
    assert {r.label: r.track_id for r in result2} == ids_by_label


def test_low_confidence_detection_rescues_an_existing_track_without_a_new_id() -> None:
    tracker = ByteTracker(_settings(min_hits=1, high_confidence_threshold=0.6))

    first = tracker.update(CAMERA, [_det(0, 0, 20, 20, confidence=0.9)])
    original_id = first[0].track_id

    # A detection below high_confidence_threshold but overlapping the track's
    # predicted position should still rescue (match) the existing track via
    # BYTE's stage-2 matching, not be ignored or spawn a duplicate.
    rescued = tracker.update(CAMERA, [_det(1, 1, 21, 21, confidence=0.45)])

    assert len(rescued) == 1
    assert rescued[0].track_id == original_id


def test_low_confidence_detection_alone_never_starts_a_new_track() -> None:
    tracker = ByteTracker(_settings(min_hits=1, high_confidence_threshold=0.6))

    # No existing tracks; a low-confidence-only detection must not create one.
    result = tracker.update(CAMERA, [_det(0, 0, 20, 20, confidence=0.45)])
    assert result == []

    # A subsequent high-confidence detection proves no track was silently
    # created above (it gets the first ID, track_id 1).
    next_result = tracker.update(CAMERA, [_det(100, 100, 120, 120, confidence=0.9)])
    assert next_result[0].track_id == 1


def test_reset_clears_camera_state() -> None:
    tracker = ByteTracker(_settings(min_hits=1))

    tracker.update(CAMERA, [_det(0, 0, 20, 20)])
    tracker.reset(CAMERA)

    fresh = tracker.update(CAMERA, [_det(0, 0, 20, 20)])

    assert fresh[0].track_id == 1


def test_reset_of_unknown_camera_is_a_no_op() -> None:
    tracker = ByteTracker(_settings())
    tracker.reset("never-seen-camera")  # must not raise
