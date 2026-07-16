"""ROI-aware rules: restricted_area_intrusion and tripwire_crossing.

Both read regions off `EventContext.regions` (populated from a camera's
configured `Region`s — see `core.entities.camera`). A registered camera's
regions are used automatically for a live stream (`StreamManager._run()`
passes `camera.regions` into the pipeline every frame); a one-shot
`POST /detect/video` upload has no registered camera to read regions from,
so it accepts an optional `regions_json` form field as a direct,
ad-hoc alternative.
"""

from __future__ import annotations

from sentinel_detect.config.settings import EventRuleSettings
from sentinel_detect.core.entities.camera import RegionType
from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.entities.geometry import Point
from sentinel_detect.core.interfaces.event_rule import (
    BaseEventRule,
    EventContext,
    event_rule_registry,
)
from sentinel_detect.events.base import Cooldown


@event_rule_registry.register("restricted_area_intrusion")
class RestrictedAreaIntrusionRule(BaseEventRule):
    """Raises an event per restricted zone that currently contains any tracked object."""

    rule_key = "restricted_area_intrusion"

    def __init__(self, settings: EventRuleSettings) -> None:
        self._cooldown = Cooldown(settings.cooldown_seconds)

    def evaluate(self, context: EventContext) -> list[Event]:
        events: list[Event] = []
        for region in context.regions:
            if region.type is not RegionType.RESTRICTED_ZONE or region.polygon is None:
                continue

            intruders = [
                t for t in context.tracked_objects if region.polygon.contains_point(t.bbox.center)
            ]
            if not intruders:
                continue

            key = f"{context.camera_id}:{region.id}"
            if not self._cooldown.ready(key, context.timestamp):
                continue
            self._cooldown.mark(key, context.timestamp)

            events.append(
                Event(
                    camera_id=context.camera_id,
                    type=EventType.RESTRICTED_AREA_INTRUSION,
                    severity=EventSeverity.CRITICAL,
                    rule=self.rule_key,
                    track_ids=tuple(t.track_id for t in intruders),
                    region_id=region.id,
                    message=f"{len(intruders)} object(s) inside restricted zone '{region.name}'",
                    timestamp=context.timestamp,
                )
            )
        return events


def _side(line: tuple[Point, Point], point: Point) -> float:
    """Signed area of the triangle (line[0], line[1], point).

    Positive/negative indicates which side of the line `point` is on; a sign
    change between two frames means the point crossed the line.
    """
    return (line[1].x - line[0].x) * (point.y - line[0].y) - (line[1].y - line[0].y) * (
        point.x - line[0].x
    )


@event_rule_registry.register("tripwire_crossing")
class TripwireCrossingRule(BaseEventRule):
    """Raises PERSON_ENTERING/PERSON_LEAVING when a person's track crosses a tripwire.

    Direction is determined by which way the sign of `_side` flips between
    the previous and current frame for that (region, track) pair — an
    arbitrary but consistent convention (negative-to-positive is "entering").
    """

    rule_key = "tripwire_crossing"

    def __init__(self, settings: EventRuleSettings) -> None:
        self._cooldown = Cooldown(settings.cooldown_seconds)
        self._last_side: dict[tuple[str, int], float] = {}

    def evaluate(self, context: EventContext) -> list[Event]:
        tripwires = [
            r for r in context.regions if r.type is RegionType.TRIPWIRE and r.line is not None
        ]
        if not tripwires:
            return []

        events: list[Event] = []
        seen_this_frame: set[tuple[str, int]] = set()

        for region in tripwires:
            assert region.line is not None
            for track in context.tracked_objects:
                if track.label is not DetectionClass.PERSON:
                    continue

                state_key = (region.id, track.track_id)
                seen_this_frame.add(state_key)
                current_side = _side(region.line, track.bbox.center)
                previous_side = self._last_side.get(state_key)
                self._last_side[state_key] = current_side

                if previous_side is None or previous_side == 0 or current_side == 0:
                    continue
                if (previous_side > 0) == (current_side > 0):
                    continue  # same side: no crossing

                cooldown_key = f"{context.camera_id}:{region.id}:{track.track_id}"
                if not self._cooldown.ready(cooldown_key, context.timestamp):
                    continue
                self._cooldown.mark(cooldown_key, context.timestamp)

                event_type = (
                    EventType.PERSON_ENTERING if previous_side < 0 else EventType.PERSON_LEAVING
                )
                events.append(
                    Event(
                        camera_id=context.camera_id,
                        type=event_type,
                        severity=EventSeverity.INFO,
                        rule=self.rule_key,
                        track_ids=(track.track_id,),
                        region_id=region.id,
                        message=f"track {track.track_id} crossed tripwire '{region.name}'",
                        timestamp=context.timestamp,
                    )
                )

        # Drop state for (region, track) pairs not observed this frame, so a
        # track that disappears and later reappears with the same ID (after
        # a gap) starts fresh instead of using stale side information.
        stale_keys = set(self._last_side) - seen_this_frame
        for stale_key in stale_keys:
            del self._last_side[stale_key]

        return events
