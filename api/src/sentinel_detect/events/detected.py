"""Simple presence rules: person/vehicle/weapon/fire/smoke detected."""

from __future__ import annotations

from sentinel_detect.core.entities.detection import DetectionClass
from sentinel_detect.core.entities.event import EventSeverity, EventType
from sentinel_detect.core.interfaces.event_rule import event_rule_registry
from sentinel_detect.events.base import LabelPresenceRule


@event_rule_registry.register("person_detected")
class PersonDetectedRule(LabelPresenceRule):
    rule_key = "person_detected"
    event_type = EventType.PERSON_DETECTED
    severity = EventSeverity.INFO
    labels = frozenset({DetectionClass.PERSON})


@event_rule_registry.register("vehicle_detected")
class VehicleDetectedRule(LabelPresenceRule):
    rule_key = "vehicle_detected"
    event_type = EventType.VEHICLE_DETECTED
    severity = EventSeverity.INFO
    labels = frozenset(
        {
            DetectionClass.CAR,
            DetectionClass.BUS,
            DetectionClass.TRUCK,
            DetectionClass.MOTORCYCLE,
            DetectionClass.BICYCLE,
        }
    )


@event_rule_registry.register("weapon_detected")
class WeaponDetectedRule(LabelPresenceRule):
    rule_key = "weapon_detected"
    event_type = EventType.WEAPON_DETECTED
    severity = EventSeverity.CRITICAL
    labels = frozenset({DetectionClass.GUN, DetectionClass.RIFLE, DetectionClass.KNIFE})


@event_rule_registry.register("fire_detected")
class FireDetectedRule(LabelPresenceRule):
    rule_key = "fire_detected"
    event_type = EventType.FIRE_DETECTED
    severity = EventSeverity.CRITICAL
    labels = frozenset({DetectionClass.FIRE, DetectionClass.FLAME})


@event_rule_registry.register("smoke_detected")
class SmokeDetectedRule(LabelPresenceRule):
    rule_key = "smoke_detected"
    event_type = EventType.SMOKE_DETECTED
    severity = EventSeverity.WARNING
    labels = frozenset({DetectionClass.SMOKE})
