"""Event rule port (Phase 4: the rule engine)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sentinel_detect.core.entities.camera import Region
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.core.registry import Registry


@dataclass(slots=True, frozen=True)
class EventContext:
    """Everything a rule needs to decide whether to raise an `Event` this frame."""

    camera_id: str
    tracked_objects: tuple[TrackedObject, ...]
    regions: tuple[Region, ...]
    timestamp: datetime


class BaseEventRule(ABC):
    """Port for a single rule that inspects tracked objects and may raise events.

    Rules are pure functions of an `EventContext`; any state a rule needs
    across frames (e.g. how long a track has lingered, for loitering) must be
    owned and persisted by the rule implementation itself, keyed by
    `camera_id`/`track_id`.
    """

    @abstractmethod
    def evaluate(self, context: EventContext) -> list[Event]:
        """Inspect `context` and return zero or more events raised this frame."""


event_rule_registry: Registry[BaseEventRule] = Registry("event_rule")
