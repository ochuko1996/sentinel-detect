import pytest

from sentinel_detect.core.entities import (
    BoundingBox,
    Detection,
    DetectionClass,
    Point,
    Polygon,
    TrackedObject,
)


def test_bounding_box_rejects_degenerate_box() -> None:
    with pytest.raises(ValueError, match="invalid box"):
        BoundingBox(x1=10, y1=10, x2=10, y2=20)


def test_bounding_box_geometry() -> None:
    box = BoundingBox(x1=0, y1=0, x2=10, y2=20)

    assert box.width == 10
    assert box.height == 20
    assert box.area == 200
    assert box.center == Point(x=5, y=10)


def test_bounding_box_iou_of_identical_boxes_is_one() -> None:
    box = BoundingBox(x1=0, y1=0, x2=10, y2=10)

    assert box.iou(box) == pytest.approx(1.0)


def test_bounding_box_iou_of_disjoint_boxes_is_zero() -> None:
    a = BoundingBox(x1=0, y1=0, x2=10, y2=10)
    b = BoundingBox(x1=100, y1=100, x2=110, y2=110)

    assert a.iou(b) == 0.0


def test_polygon_requires_at_least_three_points() -> None:
    with pytest.raises(ValueError, match="at least 3 points"):
        Polygon(points=(Point(x=0, y=0), Point(x=1, y=1)))


def test_polygon_contains_point() -> None:
    square = Polygon(
        points=(
            Point(x=0, y=0),
            Point(x=10, y=0),
            Point(x=10, y=10),
            Point(x=0, y=10),
        )
    )

    assert square.contains_point(Point(x=5, y=5)) is True
    assert square.contains_point(Point(x=50, y=50)) is False


def test_detection_requires_confidence_in_unit_range() -> None:
    box = BoundingBox(x1=0, y1=0, x2=10, y2=10)

    with pytest.raises(ValueError):
        Detection(
            camera_id="cam-1",
            detector="person",
            label=DetectionClass.PERSON,
            confidence=1.5,
            bbox=box,
            frame_width=1920,
            frame_height=1080,
        )


def test_tracked_object_from_detection_starts_as_new_with_one_hit() -> None:
    box = BoundingBox(x1=0, y1=0, x2=10, y2=10)
    detection = Detection(
        camera_id="cam-1",
        detector="person",
        label=DetectionClass.PERSON,
        confidence=0.9,
        bbox=box,
        frame_width=1920,
        frame_height=1080,
    )

    tracked = TrackedObject.from_detection(detection, track_id=42)

    assert tracked.track_id == 42
    assert tracked.hits == 1
    assert tracked.age == 0
    assert tracked.label is DetectionClass.PERSON
