"""Internal mutable per-track state.

`Track` never leaves the `tracking` package — `ByteTracker.update()` converts
it to an immutable `core.entities.TrackedObject` before returning, keeping
Kalman-filter internals out of the domain model.
"""

from __future__ import annotations

from datetime import datetime

from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.tracking import TrackedObject, TrackState
from sentinel_detect.tracking.kalman_filter import KalmanBoxFilter


class Track:
    def __init__(self, track_id: int, camera_id: str, detection: Detection) -> None:
        self.track_id = track_id
        self.camera_id = camera_id
        self.label: DetectionClass = detection.label
        self.confidence = detection.confidence
        self.kalman = KalmanBoxFilter(detection.bbox)
        self.hits = 1
        self.age = 0
        self.time_since_update = 0
        self.first_seen: datetime = detection.timestamp
        self.last_seen: datetime = detection.timestamp

    def predict(self) -> None:
        self.kalman.predict()
        self.age += 1
        self.time_since_update += 1

    def mark_matched(self, detection: Detection) -> None:
        self.kalman.update(detection.bbox)
        self.confidence = detection.confidence
        self.last_seen = detection.timestamp
        self.hits += 1
        self.time_since_update = 0

    def is_confirmed(self, min_hits: int) -> bool:
        return self.hits >= min_hits

    def to_tracked_object(self) -> TrackedObject:
        state = TrackState.TRACKED if self.time_since_update == 0 else TrackState.LOST
        return TrackedObject(
            track_id=self.track_id,
            camera_id=self.camera_id,
            label=self.label,
            confidence=self.confidence,
            bbox=self.kalman.bbox,
            state=state,
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            hits=self.hits,
            age=self.age,
        )
