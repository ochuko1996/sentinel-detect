"""Entities produced by the object tracking stage (Phase 3)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox


class TrackState(StrEnum):
    """Lifecycle state of a tracked object, mirroring ByteTrack/DeepSORT semantics."""

    NEW = "new"
    TRACKED = "tracked"
    LOST = "lost"
    REMOVED = "removed"


class TrackedObject(BaseModel, frozen=True):
    """A `Detection` associated with a persistent identity across frames."""

    track_id: int
    camera_id: str
    label: DetectionClass
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    state: TrackState
    first_seen: datetime
    last_seen: datetime
    hits: int = Field(ge=0, description="Number of frames this track has been matched.")
    age: int = Field(ge=0, description="Number of frames since this track was created.")

    @classmethod
    def from_detection(cls, detection: Detection, track_id: int) -> TrackedObject:
        return cls(
            track_id=track_id,
            camera_id=detection.camera_id,
            label=detection.label,
            confidence=detection.confidence,
            bbox=detection.bbox,
            state=TrackState.NEW,
            first_seen=detection.timestamp,
            last_seen=detection.timestamp,
            hits=1,
            age=0,
        )
