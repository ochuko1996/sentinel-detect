"""Object tracking port (Phase 3: ByteTrack / DeepSORT implementations)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel_detect.core.entities.detection import Detection
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.core.registry import Registry


class BaseTracker(ABC):
    """Port for assigning persistent identities to per-frame detections.

    Implementations keep internal per-camera state; `reset` clears it (e.g.
    when a camera reconnects after a stream drop).
    """

    @abstractmethod
    def update(self, camera_id: str, detections: list[Detection]) -> list[TrackedObject]:
        """Associate `detections` with existing tracks for `camera_id` and return the result."""

    @abstractmethod
    def reset(self, camera_id: str) -> None:
        """Discard all track state for `camera_id`."""


tracker_registry: Registry[BaseTracker] = Registry("tracker")
