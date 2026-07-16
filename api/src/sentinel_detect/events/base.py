"""Shared building blocks for built-in event rules.

Every concrete rule takes exactly one constructor argument,
`EventRuleSettings`, so `events/factory.py` can build any of them uniformly
— the same pattern `ByteTracker(TrackingSettings)` uses for the tracker.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sentinel_detect.config.settings import EventRuleSettings
from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.interfaces.event_rule import BaseEventRule, EventContext


class Cooldown:
    """Per-key last-fired timestamps.

    Without this, a rule whose trigger condition holds for 200 consecutive
    frames would raise 200 events. `ready`/`mark` let a rule re-fire for a
    given key (e.g. a camera_id, or a `camera_id:track_id` pair) at most
    once per `seconds`.
    """

    def __init__(self, seconds: float) -> None:
        self._seconds = seconds
        self._last_fired: dict[str, datetime] = {}

    def ready(self, key: str, now: datetime) -> bool:
        last = self._last_fired.get(key)
        return last is None or (now - last).total_seconds() >= self._seconds

    def mark(self, key: str, now: datetime) -> None:
        self._last_fired[key] = now


class LabelPresenceRule(BaseEventRule):
    """Raises one event per evaluation while any tracked object matches `labels`.

    Concrete subclasses set `rule_key`, `event_type`, `severity`, and
    `labels`; this covers person/vehicle/weapon/fire/smoke-detected.
    """

    rule_key: ClassVar[str]
    event_type: ClassVar[EventType]
    severity: ClassVar[EventSeverity]
    labels: ClassVar[frozenset[DetectionClass]]

    def __init__(self, settings: EventRuleSettings) -> None:
        self._cooldown = Cooldown(settings.cooldown_seconds)

    def evaluate(self, context: EventContext) -> list[Event]:
        matching = [t for t in context.tracked_objects if t.label in self.labels]
        if not matching:
            return []
        if not self._cooldown.ready(context.camera_id, context.timestamp):
            return []
        self._cooldown.mark(context.camera_id, context.timestamp)

        labels_seen = sorted({m.label.value for m in matching})
        return [
            Event(
                camera_id=context.camera_id,
                type=self.event_type,
                severity=self.severity,
                rule=self.rule_key,
                track_ids=tuple(m.track_id for m in matching),
                message=f"{', '.join(labels_seen)} detected ({len(matching)} object(s))",
                timestamp=context.timestamp,
            )
        ]


class PersonCountThresholdRule(BaseEventRule):
    """Raises one event per evaluation while the number of PERSON tracks
    meets or exceeds a threshold. Covers multiple_people/crowd_detected."""

    rule_key: ClassVar[str]
    event_type: ClassVar[EventType]
    severity: ClassVar[EventSeverity]
    default_min_count: ClassVar[int]

    def __init__(self, settings: EventRuleSettings) -> None:
        self._cooldown = Cooldown(settings.cooldown_seconds)
        self._min_count = int(settings.params.get("min_count", self.default_min_count))

    def evaluate(self, context: EventContext) -> list[Event]:
        people = [t for t in context.tracked_objects if t.label is DetectionClass.PERSON]
        if len(people) < self._min_count:
            return []
        if not self._cooldown.ready(context.camera_id, context.timestamp):
            return []
        self._cooldown.mark(context.camera_id, context.timestamp)

        return [
            Event(
                camera_id=context.camera_id,
                type=self.event_type,
                severity=self.severity,
                rule=self.rule_key,
                track_ids=tuple(p.track_id for p in people),
                message=f"{len(people)} people present (threshold {self._min_count})",
                timestamp=context.timestamp,
            )
        ]
