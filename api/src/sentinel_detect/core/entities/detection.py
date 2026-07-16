"""Detection taxonomy and the Detection entity produced by the inference pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from sentinel_detect.core.entities.geometry import BoundingBox


class DetectionClass(StrEnum):
    """Every object class SENTINEL Detect's built-in detectors can emit.

    New detector modules extend this enum; nothing else in `core` needs to
    change because detectors, events, and storage all key off this value
    rather than per-detector class lists.
    """

    # Person detection
    PERSON = "person"

    # Vehicle detection
    CAR = "car"
    BUS = "bus"
    TRUCK = "truck"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"

    # Weapon detection
    GUN = "gun"
    RIFLE = "rifle"
    KNIFE = "knife"

    # Fire detection
    FIRE = "fire"
    FLAME = "flame"

    # Smoke detection
    SMOKE = "smoke"

    # PPE detection
    HARD_HAT = "hard_hat"
    SAFETY_VEST = "safety_vest"
    GLOVES = "gloves"
    SAFETY_GLASSES = "safety_glasses"

    # Animal detection
    DOG = "dog"
    CAT = "cat"
    COW = "cow"
    GOAT = "goat"
    HORSE = "horse"


class Detection(BaseModel, frozen=True):
    """A single detected object in a single frame, prior to tracking."""

    id: UUID = Field(default_factory=uuid4)
    camera_id: str
    detector: str
    """Key of the detector module that produced this detection (e.g. 'weapon')."""
    label: DetectionClass
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
