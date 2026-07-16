import pytest

from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.tracking.kalman_filter import KalmanBoxFilter


def test_bbox_immediately_after_construction_matches_the_initial_measurement() -> None:
    box = BoundingBox(x1=10, y1=10, x2=30, y2=50)
    kalman = KalmanBoxFilter(box)

    result = kalman.bbox

    assert result.center.x == pytest.approx(box.center.x, abs=1e-6)
    assert result.center.y == pytest.approx(box.center.y, abs=1e-6)
    assert result.width == pytest.approx(box.width, abs=1e-6)
    assert result.height == pytest.approx(box.height, abs=1e-6)


def test_predict_without_updates_extrapolates_zero_velocity_as_no_movement() -> None:
    box = BoundingBox(x1=10, y1=10, x2=30, y2=50)
    kalman = KalmanBoxFilter(box)

    kalman.predict()

    # No velocity has been observed yet, so a bare predict() shouldn't move the box.
    assert kalman.bbox.center.x == pytest.approx(box.center.x, abs=1e-6)
    assert kalman.bbox.center.y == pytest.approx(box.center.y, abs=1e-6)


def test_filter_tracks_a_smoothly_moving_box() -> None:
    kalman = KalmanBoxFilter(BoundingBox(x1=0, y1=0, x2=20, y2=20))

    # Feed a sequence of measurements moving steadily right; each step:
    # predict (extrapolate motion), then update (correct with observation).
    for step in range(1, 6):
        dx = step * 10
        kalman.predict()
        kalman.update(BoundingBox(x1=dx, y1=0, x2=dx + 20, y2=20))

    # After several consistent observations, the filter should have picked up
    # the rightward velocity and its corrected position should be close to
    # the last true measurement.
    assert kalman.bbox.center.x == pytest.approx(60.0, abs=3.0)
    assert kalman.bbox.center.y == pytest.approx(10.0, abs=3.0)


def test_predict_after_learning_velocity_extrapolates_forward() -> None:
    kalman = KalmanBoxFilter(BoundingBox(x1=0, y1=0, x2=20, y2=20))

    for step in range(1, 6):
        dx = step * 10
        kalman.predict()
        kalman.update(BoundingBox(x1=dx, y1=0, x2=dx + 20, y2=20))

    before = kalman.bbox.center.x
    kalman.predict()
    after = kalman.bbox.center.x

    # Having learned a rightward velocity, an additional predict() with no
    # update should move the box further right, not leave it in place.
    assert after > before
