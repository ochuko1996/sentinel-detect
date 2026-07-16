"""Object abandoned / object removed.

Both rules are class-agnostic (they run over any non-PERSON tracked
object) because this platform has no dedicated "unattended bag/luggage"
detector — no free pretrained model provides one, the same story as
weapon/fire/PPE (see docs/architecture.md). They become semantically sharp
once such a detector exists; today they're honest, generic infrastructure
that works correctly on whatever non-person classes are actually tracked
(e.g. a vehicle parked motionless in a restricted lane).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sentinel_detect.config.settings import EventRuleSettings
from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.entities.geometry import Point
from sentinel_detect.core.entities.tracking import TrackedObject
from sentinel_detect.core.interfaces.event_rule import (
    BaseEventRule,
    EventContext,
    event_rule_registry,
)

_DEFAULT_STATIONARY_SECONDS = 30.0
_DEFAULT_MOVEMENT_THRESHOLD_PX = 20.0
_DEFAULT_MIN_HITS = 5


@dataclass
class _Anchor:
    center: Point
    since: datetime
    fired: bool = False


@event_rule_registry.register("object_abandoned")
class ObjectAbandonedRule(BaseEventRule):
    """A non-person track whose position hasn't moved beyond a small pixel
    threshold for `stationary_seconds` fires once (per track_id)."""

    rule_key = "object_abandoned"

    def __init__(self, settings: EventRuleSettings) -> None:
        self._stationary_seconds = settings.params.get(
            "stationary_seconds", _DEFAULT_STATIONARY_SECONDS
        )
        self._movement_threshold = settings.params.get(
            "movement_threshold_px", _DEFAULT_MOVEMENT_THRESHOLD_PX
        )
        self._anchors: dict[str, dict[int, _Anchor]] = defaultdict(dict)

    def evaluate(self, context: EventContext) -> list[Event]:
        camera_anchors = self._anchors[context.camera_id]
        present_ids: set[int] = set()
        events: list[Event] = []

        for track in context.tracked_objects:
            if track.label is DetectionClass.PERSON:
                continue
            present_ids.add(track.track_id)

            center = track.bbox.center
            anchor = camera_anchors.get(track.track_id)
            if anchor is None:
                camera_anchors[track.track_id] = _Anchor(center=center, since=context.timestamp)
                continue

            distance = math.hypot(center.x - anchor.center.x, center.y - anchor.center.y)
            if distance > self._movement_threshold:
                camera_anchors[track.track_id] = _Anchor(center=center, since=context.timestamp)
                continue

            if anchor.fired:
                continue

            dwell = (context.timestamp - anchor.since).total_seconds()
            if dwell < self._stationary_seconds:
                continue

            anchor.fired = True
            events.append(
                Event(
                    camera_id=context.camera_id,
                    type=EventType.OBJECT_ABANDONED,
                    severity=EventSeverity.WARNING,
                    rule=self.rule_key,
                    track_ids=(track.track_id,),
                    message=(
                        f"{track.label.value} (track {track.track_id}) "
                        f"stationary for {dwell:.0f}s"
                    ),
                    timestamp=context.timestamp,
                )
            )

        for stale_id in set(camera_anchors) - present_ids:
            del camera_anchors[stale_id]

        return events


@event_rule_registry.register("object_removed")
class ObjectRemovedRule(BaseEventRule):
    """A non-person track that had been stably tracked (>= min_hits) and
    then disappears from one frame to the next fires once.

    This is a "stably-present-then-gone" heuristic, not a true
    background-subtraction "static object vanished" detector — the latter
    needs pixel-level scene modeling this platform doesn't yet do.
    """

    rule_key = "object_removed"

    def __init__(self, settings: EventRuleSettings) -> None:
        self._min_hits = int(settings.params.get("min_hits", _DEFAULT_MIN_HITS))
        self._last_seen: dict[str, dict[int, TrackedObject]] = defaultdict(dict)

    def evaluate(self, context: EventContext) -> list[Event]:
        previous = self._last_seen[context.camera_id]
        current = {
            t.track_id: t for t in context.tracked_objects if t.label is not DetectionClass.PERSON
        }

        events: list[Event] = []
        for track_id, last_known in previous.items():
            if track_id in current:
                continue
            if last_known.hits < self._min_hits:
                continue
            events.append(
                Event(
                    camera_id=context.camera_id,
                    type=EventType.OBJECT_REMOVED,
                    severity=EventSeverity.WARNING,
                    rule=self.rule_key,
                    track_ids=(track_id,),
                    message=(
                        f"{last_known.label.value} (track {track_id}) removed after "
                        f"{last_known.hits} tracked frames"
                    ),
                    timestamp=context.timestamp,
                )
            )

        self._last_seen[context.camera_id] = current
        return events
