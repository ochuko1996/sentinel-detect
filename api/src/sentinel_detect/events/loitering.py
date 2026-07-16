"""Loitering: a person present for longer than a dwell threshold."""

from __future__ import annotations

from sentinel_detect.config.settings import EventRuleSettings
from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.interfaces.event_rule import (
    BaseEventRule,
    EventContext,
    event_rule_registry,
)
from sentinel_detect.events.base import Cooldown

_DEFAULT_DWELL_SECONDS = 60.0


@event_rule_registry.register("loitering")
class LoiteringRule(BaseEventRule):
    """A track's dwell time is `last_seen - first_seen` on the `TrackedObject`
    itself (maintained by the tracker), so this rule needs no per-track state
    of its own — only the cooldown to avoid re-firing every frame."""

    rule_key = "loitering"

    def __init__(self, settings: EventRuleSettings) -> None:
        self._cooldown = Cooldown(settings.cooldown_seconds)
        self._dwell_seconds = settings.params.get("dwell_seconds", _DEFAULT_DWELL_SECONDS)

    def evaluate(self, context: EventContext) -> list[Event]:
        events: list[Event] = []
        for track in context.tracked_objects:
            if track.label is not DetectionClass.PERSON:
                continue

            dwell = (context.timestamp - track.first_seen).total_seconds()
            if dwell < self._dwell_seconds:
                continue

            key = f"{context.camera_id}:{track.track_id}"
            if not self._cooldown.ready(key, context.timestamp):
                continue
            self._cooldown.mark(key, context.timestamp)

            events.append(
                Event(
                    camera_id=context.camera_id,
                    type=EventType.LOITERING,
                    severity=EventSeverity.WARNING,
                    rule=self.rule_key,
                    track_ids=(track.track_id,),
                    message=(
                        f"track {track.track_id} present for {dwell:.0f}s "
                        f"(>= {self._dwell_seconds:.0f}s)"
                    ),
                    timestamp=context.timestamp,
                )
            )
        return events
