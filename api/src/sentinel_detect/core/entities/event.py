"""Event entities produced by the rule engine (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Security-relevant occurrences the rule engine can raise.

    New rule modules extend this enum rather than inventing ad-hoc strings,
    so alerts/storage/API consumers have a closed, typed vocabulary.
    """

    PERSON_DETECTED = "person_detected"
    VEHICLE_DETECTED = "vehicle_detected"
    WEAPON_DETECTED = "weapon_detected"
    FIRE_DETECTED = "fire_detected"
    SMOKE_DETECTED = "smoke_detected"
    RESTRICTED_AREA_INTRUSION = "restricted_area_intrusion"
    LOITERING = "loitering"
    CROWD_DETECTED = "crowd_detected"
    OBJECT_ABANDONED = "object_abandoned"
    OBJECT_REMOVED = "object_removed"
    MULTIPLE_PEOPLE = "multiple_people"
    PERSON_ENTERING = "person_entering"
    PERSON_LEAVING = "person_leaving"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Event(BaseModel, frozen=True):
    """A rule-engine occurrence, referencing the track(s) that triggered it."""

    id: UUID = Field(default_factory=uuid4)
    camera_id: str
    type: EventType
    severity: EventSeverity
    rule: str
    """Key of the event rule that raised this event."""
    track_ids: tuple[int, ...] = Field(default_factory=tuple)
    region_id: str | None = None
    message: str
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
