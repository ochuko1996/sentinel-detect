from datetime import UTC, datetime, timedelta

from sentinel_detect.config.settings import EventRuleSettings
from sentinel_detect.core.entities.camera import Region, RegionType
from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.event import EventSeverity, EventType
from sentinel_detect.core.entities.geometry import BoundingBox, Point, Polygon
from sentinel_detect.core.entities.tracking import TrackedObject, TrackState
from sentinel_detect.core.interfaces.event_rule import EventContext
from sentinel_detect.events.crowd import CrowdDetectedRule, MultiplePeopleRule
from sentinel_detect.events.detected import (
    FireDetectedRule,
    PersonDetectedRule,
    SmokeDetectedRule,
    VehicleDetectedRule,
    WeaponDetectedRule,
)
from sentinel_detect.events.loitering import LoiteringRule
from sentinel_detect.events.object_state import ObjectAbandonedRule, ObjectRemovedRule
from sentinel_detect.events.regions import RestrictedAreaIntrusionRule, TripwireCrossingRule

CAMERA = "cam-1"
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _settings(cooldown_seconds: float = 0.0, **params: float) -> EventRuleSettings:
    return EventRuleSettings(cooldown_seconds=cooldown_seconds, params=params)


def _track(
    track_id: int,
    label: DetectionClass,
    *,
    x1: float = 0,
    y1: float = 0,
    x2: float = 20,
    y2: float = 20,
    first_seen: datetime = T0,
    last_seen: datetime = T0,
    hits: int = 3,
) -> TrackedObject:
    return TrackedObject(
        track_id=track_id,
        camera_id=CAMERA,
        label=label,
        confidence=0.9,
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        state=TrackState.TRACKED,
        first_seen=first_seen,
        last_seen=last_seen,
        hits=hits,
        age=hits,
    )


def _context(
    tracked_objects: tuple[TrackedObject, ...],
    regions: tuple[Region, ...] = (),
    timestamp: datetime = T0,
) -> EventContext:
    return EventContext(
        camera_id=CAMERA, tracked_objects=tracked_objects, regions=regions, timestamp=timestamp
    )


# --- LabelPresenceRule-based rules ---------------------------------------


def test_person_detected_rule_fires_when_a_person_is_tracked() -> None:
    rule = PersonDetectedRule(_settings())
    events = rule.evaluate(_context((_track(1, DetectionClass.PERSON),)))

    assert len(events) == 1
    assert events[0].type is EventType.PERSON_DETECTED
    assert events[0].track_ids == (1,)


def test_person_detected_rule_is_silent_with_no_person_tracks() -> None:
    rule = PersonDetectedRule(_settings())
    events = rule.evaluate(_context((_track(1, DetectionClass.CAR),)))
    assert events == []


def test_vehicle_detected_rule_matches_any_vehicle_class() -> None:
    rule = VehicleDetectedRule(_settings())
    for label in (
        DetectionClass.CAR,
        DetectionClass.BUS,
        DetectionClass.TRUCK,
        DetectionClass.MOTORCYCLE,
        DetectionClass.BICYCLE,
    ):
        events = rule.evaluate(_context((_track(1, label),)))
        assert len(events) == 1
        assert events[0].type is EventType.VEHICLE_DETECTED


def test_weapon_detected_rule_is_critical_severity() -> None:
    rule = WeaponDetectedRule(_settings())
    events = rule.evaluate(_context((_track(1, DetectionClass.GUN),)))
    assert events[0].severity is EventSeverity.CRITICAL


def test_fire_detected_rule_matches_fire_and_flame() -> None:
    rule = FireDetectedRule(_settings())
    assert len(rule.evaluate(_context((_track(1, DetectionClass.FIRE),)))) == 1
    assert len(rule.evaluate(_context((_track(2, DetectionClass.FLAME),)))) == 1


def test_smoke_detected_rule_is_warning_severity() -> None:
    rule = SmokeDetectedRule(_settings())
    events = rule.evaluate(_context((_track(1, DetectionClass.SMOKE),)))
    assert events[0].severity is EventSeverity.WARNING


def test_presence_rule_respects_cooldown() -> None:
    rule = PersonDetectedRule(_settings(cooldown_seconds=60.0))

    first = rule.evaluate(_context((_track(1, DetectionClass.PERSON),), timestamp=T0))
    second = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON),), timestamp=T0 + timedelta(seconds=1))
    )
    third = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON),), timestamp=T0 + timedelta(seconds=61))
    )

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


# --- PersonCountThresholdRule-based rules --------------------------------


def test_multiple_people_rule_fires_at_default_threshold_of_two() -> None:
    rule = MultiplePeopleRule(_settings())

    below = rule.evaluate(_context((_track(1, DetectionClass.PERSON),)))
    at_threshold = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON), _track(2, DetectionClass.PERSON)))
    )

    assert below == []
    assert len(at_threshold) == 1
    assert at_threshold[0].type is EventType.MULTIPLE_PEOPLE


def test_crowd_detected_rule_uses_configured_min_count() -> None:
    rule = CrowdDetectedRule(_settings(min_count=3))

    two_people = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON), _track(2, DetectionClass.PERSON)))
    )
    three_people = rule.evaluate(
        _context(
            (
                _track(1, DetectionClass.PERSON),
                _track(2, DetectionClass.PERSON),
                _track(3, DetectionClass.PERSON),
            )
        )
    )

    assert two_people == []
    assert len(three_people) == 1
    assert three_people[0].type is EventType.CROWD_DETECTED


def test_multiple_people_rule_respects_cooldown() -> None:
    rule = MultiplePeopleRule(_settings(cooldown_seconds=60.0))
    two_people = (_track(1, DetectionClass.PERSON), _track(2, DetectionClass.PERSON))

    first = rule.evaluate(_context(two_people, timestamp=T0))
    second = rule.evaluate(_context(two_people, timestamp=T0 + timedelta(seconds=1)))
    third = rule.evaluate(_context(two_people, timestamp=T0 + timedelta(seconds=61)))

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


# --- Region rules ---------------------------------------------------------


def _restricted_zone(region_id: str = "zone-1") -> Region:
    return Region(
        id=region_id,
        camera_id=CAMERA,
        name="Restricted Zone",
        type=RegionType.RESTRICTED_ZONE,
        polygon=Polygon(
            points=(Point(x=0, y=0), Point(x=100, y=0), Point(x=100, y=100), Point(x=0, y=100))
        ),
    )


def test_restricted_area_intrusion_fires_when_a_track_is_inside_the_polygon() -> None:
    rule = RestrictedAreaIntrusionRule(_settings())
    zone = _restricted_zone()

    inside = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=40, y1=40, x2=60, y2=60),), (zone,))
    )
    outside = rule.evaluate(
        _context((_track(2, DetectionClass.PERSON, x1=200, y1=200, x2=220, y2=220),), (zone,))
    )

    assert len(inside) == 1
    assert inside[0].type is EventType.RESTRICTED_AREA_INTRUSION
    assert inside[0].region_id == "zone-1"
    assert outside == []


def test_restricted_area_intrusion_is_a_no_op_without_regions() -> None:
    rule = RestrictedAreaIntrusionRule(_settings())
    events = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=40, y1=40, x2=60, y2=60),), ())
    )
    assert events == []


def test_restricted_area_intrusion_ignores_non_restricted_zone_regions() -> None:
    rule = RestrictedAreaIntrusionRule(_settings())
    wire = Region(
        id="wire-1",
        camera_id=CAMERA,
        name="Doorway",
        type=RegionType.TRIPWIRE,
        line=(Point(x=50, y=0), Point(x=50, y=100)),
    )

    events = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=40, y1=40, x2=60, y2=60),), (wire,))
    )

    assert events == []


def test_restricted_area_intrusion_respects_cooldown() -> None:
    rule = RestrictedAreaIntrusionRule(_settings(cooldown_seconds=60.0))
    zone = _restricted_zone()
    track = _track(1, DetectionClass.PERSON, x1=40, y1=40, x2=60, y2=60)

    first = rule.evaluate(_context((track,), (zone,), timestamp=T0))
    second = rule.evaluate(_context((track,), (zone,), timestamp=T0 + timedelta(seconds=1)))
    third = rule.evaluate(_context((track,), (zone,), timestamp=T0 + timedelta(seconds=61)))

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


def _tripwire(region_id: str = "wire-1") -> Region:
    return Region(
        id=region_id,
        camera_id=CAMERA,
        name="Doorway",
        type=RegionType.TRIPWIRE,
        line=(Point(x=50, y=0), Point(x=50, y=100)),
    )


def test_tripwire_crossing_detects_entering_and_leaving() -> None:
    rule = TripwireCrossingRule(_settings())
    wire = _tripwire()

    # Track starts left of the line (x centers < 50)...
    rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=10, y1=40, x2=30, y2=60),), (wire,))
    )
    # ...and crosses to the right of it: a crossing should be detected.
    crossed = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=60, y1=40, x2=80, y2=60),), (wire,))
    )

    assert len(crossed) == 1
    assert crossed[0].type in (EventType.PERSON_ENTERING, EventType.PERSON_LEAVING)
    first_direction = crossed[0].type

    # Crossing back the other way should give the opposite event type.
    back = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=10, y1=40, x2=30, y2=60),), (wire,))
    )
    assert len(back) == 1
    assert back[0].type is not first_direction


def test_tripwire_crossing_does_not_fire_without_an_actual_crossing() -> None:
    rule = TripwireCrossingRule(_settings())
    wire = _tripwire()

    rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=10, y1=40, x2=30, y2=60),), (wire,))
    )
    same_side = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=15, y1=40, x2=35, y2=60),), (wire,))
    )

    assert same_side == []


def test_tripwire_crossing_ignores_non_person_tracks() -> None:
    rule = TripwireCrossingRule(_settings())
    wire = _tripwire()

    rule.evaluate(_context((_track(1, DetectionClass.CAR, x1=10, y1=40, x2=30, y2=60),), (wire,)))
    crossed = rule.evaluate(
        _context((_track(1, DetectionClass.CAR, x1=60, y1=40, x2=80, y2=60),), (wire,))
    )

    assert crossed == []


def test_tripwire_crossing_respects_cooldown() -> None:
    rule = TripwireCrossingRule(_settings(cooldown_seconds=60.0))
    wire = _tripwire()

    rule.evaluate(
        _context(
            (_track(1, DetectionClass.PERSON, x1=10, y1=40, x2=30, y2=60),), (wire,), timestamp=T0
        )
    )
    first_cross = rule.evaluate(
        _context(
            (_track(1, DetectionClass.PERSON, x1=60, y1=40, x2=80, y2=60),),
            (wire,),
            timestamp=T0 + timedelta(seconds=1),
        )
    )
    # Crosses back immediately - within the cooldown window, so suppressed.
    second_cross = rule.evaluate(
        _context(
            (_track(1, DetectionClass.PERSON, x1=10, y1=40, x2=30, y2=60),),
            (wire,),
            timestamp=T0 + timedelta(seconds=2),
        )
    )

    assert len(first_cross) == 1
    assert second_cross == []


def test_tripwire_crossing_purges_state_for_tracks_no_longer_present() -> None:
    rule = TripwireCrossingRule(_settings())
    wire = _tripwire()

    rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=10, y1=40, x2=30, y2=60),), (wire,))
    )
    rule.evaluate(_context((), (wire,)))  # track gone -> its side-history is purged

    # Reappearing on the "crossed" side should be treated as a fresh
    # sighting (no prior side to compare against), not as a crossing.
    events = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON, x1=60, y1=40, x2=80, y2=60),), (wire,))
    )

    assert events == []


# --- Loitering --------------------------------------------------------------


def test_loitering_fires_once_dwell_time_exceeds_threshold() -> None:
    rule = LoiteringRule(_settings(dwell_seconds=60.0))

    too_soon = rule.evaluate(
        _context(
            (_track(1, DetectionClass.PERSON, first_seen=T0),),
            timestamp=T0 + timedelta(seconds=30),
        )
    )
    long_enough = rule.evaluate(
        _context(
            (_track(1, DetectionClass.PERSON, first_seen=T0),),
            timestamp=T0 + timedelta(seconds=61),
        )
    )

    assert too_soon == []
    assert len(long_enough) == 1
    assert long_enough[0].type is EventType.LOITERING


def test_loitering_ignores_non_person_tracks() -> None:
    rule = LoiteringRule(_settings(dwell_seconds=60.0))

    events = rule.evaluate(
        _context(
            (_track(1, DetectionClass.CAR, first_seen=T0),), timestamp=T0 + timedelta(seconds=120)
        )
    )

    assert events == []


def test_loitering_respects_cooldown() -> None:
    rule = LoiteringRule(_settings(cooldown_seconds=60.0, dwell_seconds=60.0))
    track = _track(1, DetectionClass.PERSON, first_seen=T0)

    first = rule.evaluate(_context((track,), timestamp=T0 + timedelta(seconds=61)))
    second = rule.evaluate(_context((track,), timestamp=T0 + timedelta(seconds=62)))

    assert len(first) == 1
    assert second == []


# --- Object abandoned / removed ---------------------------------------------


def test_object_abandoned_fires_once_a_stationary_object_exceeds_the_threshold() -> None:
    rule = ObjectAbandonedRule(_settings(stationary_seconds=30.0, movement_threshold_px=5.0))

    rule.evaluate(
        _context((_track(1, DetectionClass.CAR, x1=0, y1=0, x2=20, y2=20),), timestamp=T0)
    )
    too_soon = rule.evaluate(
        _context(
            (_track(1, DetectionClass.CAR, x1=1, y1=1, x2=21, y2=21),),
            timestamp=T0 + timedelta(seconds=10),
        )
    )
    fired = rule.evaluate(
        _context(
            (_track(1, DetectionClass.CAR, x1=1, y1=1, x2=21, y2=21),),
            timestamp=T0 + timedelta(seconds=31),
        )
    )
    # Once fired, it should not fire again for the same track.
    again = rule.evaluate(
        _context(
            (_track(1, DetectionClass.CAR, x1=1, y1=1, x2=21, y2=21),),
            timestamp=T0 + timedelta(seconds=90),
        )
    )

    assert too_soon == []
    assert len(fired) == 1
    assert fired[0].type is EventType.OBJECT_ABANDONED
    assert again == []


def test_object_abandoned_resets_the_clock_if_the_object_moves() -> None:
    rule = ObjectAbandonedRule(_settings(stationary_seconds=30.0, movement_threshold_px=5.0))

    rule.evaluate(
        _context((_track(1, DetectionClass.CAR, x1=0, y1=0, x2=20, y2=20),), timestamp=T0)
    )
    # Moves significantly at t=25s: clock resets, so evaluating at t=40s
    # (only 15s after the move) should not have fired yet.
    rule.evaluate(
        _context(
            (_track(1, DetectionClass.CAR, x1=200, y1=200, x2=220, y2=220),),
            timestamp=T0 + timedelta(seconds=25),
        )
    )
    still_not_fired = rule.evaluate(
        _context(
            (_track(1, DetectionClass.CAR, x1=201, y1=201, x2=221, y2=221),),
            timestamp=T0 + timedelta(seconds=40),
        )
    )

    assert still_not_fired == []


def test_object_abandoned_ignores_person_tracks() -> None:
    rule = ObjectAbandonedRule(_settings(stationary_seconds=1.0, movement_threshold_px=5.0))

    rule.evaluate(_context((_track(1, DetectionClass.PERSON),), timestamp=T0))
    events = rule.evaluate(
        _context((_track(1, DetectionClass.PERSON),), timestamp=T0 + timedelta(seconds=10))
    )

    assert events == []


def test_object_abandoned_purges_anchors_for_tracks_no_longer_present() -> None:
    rule = ObjectAbandonedRule(_settings(stationary_seconds=10.0, movement_threshold_px=5.0))
    car = _track(1, DetectionClass.CAR, x1=0, y1=0, x2=20, y2=20)

    rule.evaluate(_context((car,), timestamp=T0))  # anchor created
    rule.evaluate(_context((), timestamp=T0 + timedelta(seconds=5)))  # car gone -> anchor purged

    # The car reappears well past the *original* stationary threshold from
    # T0, but since its anchor was purged rather than merely carried
    # forward, this is a fresh sighting - too soon to fire yet.
    events = rule.evaluate(_context((car,), timestamp=T0 + timedelta(seconds=15)))

    assert events == []


def test_object_removed_fires_when_a_stable_track_disappears() -> None:
    rule = ObjectRemovedRule(_settings(min_hits=3))

    rule.evaluate(_context((_track(1, DetectionClass.CAR, hits=5),), timestamp=T0))
    removed = rule.evaluate(_context((), timestamp=T0 + timedelta(seconds=1)))

    assert len(removed) == 1
    assert removed[0].type is EventType.OBJECT_REMOVED
    assert removed[0].track_ids == (1,)


def test_object_removed_ignores_tracks_below_min_hits() -> None:
    rule = ObjectRemovedRule(_settings(min_hits=10))

    rule.evaluate(_context((_track(1, DetectionClass.CAR, hits=2),), timestamp=T0))
    removed = rule.evaluate(_context((), timestamp=T0 + timedelta(seconds=1)))

    assert removed == []


def test_object_removed_does_not_fire_while_the_track_is_still_present() -> None:
    rule = ObjectRemovedRule(_settings(min_hits=1))

    rule.evaluate(_context((_track(1, DetectionClass.CAR, hits=5),), timestamp=T0))
    still_present = rule.evaluate(
        _context((_track(1, DetectionClass.CAR, hits=6),), timestamp=T0 + timedelta(seconds=1))
    )

    assert still_present == []
