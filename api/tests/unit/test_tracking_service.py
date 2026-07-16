import numpy as np

from sentinel_detect.config.settings import TrackingSettings
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.interfaces.detector import BaseDetector
from sentinel_detect.services.detection_service import DetectionService
from sentinel_detect.services.tracking_service import TrackingService
from sentinel_detect.tracking.byte_track import ByteTracker


class _FixedDetector(BaseDetector):
    """Always reports one PERSON detection at a fixed box."""

    def detect(self, frame: Frame) -> list[Detection]:
        return [
            Detection(
                camera_id=frame.camera_id,
                detector="person",
                label=DetectionClass.PERSON,
                confidence=0.9,
                bbox=BoundingBox(x1=0, y1=0, x2=20, y2=20),
                frame_width=frame.width,
                frame_height=frame.height,
            )
        ]


def _frame(camera_id: str, frame_index: int) -> Frame:
    return Frame(
        camera_id=camera_id, image=np.zeros((4, 4, 3), dtype=np.uint8), frame_index=frame_index
    )


def _detection_service() -> DetectionService:
    detector = _FixedDetector(None, confidence_threshold=0.1, iou_threshold=0.5)  # type: ignore[arg-type]
    return DetectionService({"person": detector})


def test_process_frame_assigns_and_persists_track_ids_across_calls() -> None:
    detection_service = _detection_service()
    tracker = ByteTracker(TrackingSettings(min_hits=1))
    service = TrackingService(detection_service, tracker)

    first_detections, first_tracked = service.process_frame(_frame("cam-1", 0))
    second_detections, second_tracked = service.process_frame(_frame("cam-1", 1))

    assert len(first_detections) == 1
    assert len(first_tracked) == 1
    assert len(second_tracked) == 1
    assert first_tracked[0].track_id == second_tracked[0].track_id


def test_reset_starts_track_ids_over_for_that_camera() -> None:
    detection_service = _detection_service()
    tracker = ByteTracker(TrackingSettings(min_hits=1))
    service = TrackingService(detection_service, tracker)

    service.process_frame(_frame("cam-1", 0))
    service.reset("cam-1")
    _, fresh_tracked = service.process_frame(_frame("cam-1", 0))

    assert fresh_tracked[0].track_id == 1


def test_active_detector_keys_passes_through_to_the_detection_service() -> None:
    detection_service = _detection_service()
    tracker = ByteTracker(TrackingSettings())
    service = TrackingService(detection_service, tracker)

    assert service.active_detector_keys() == ["person"]
