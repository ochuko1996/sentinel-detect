"""Person-count-threshold rules: multiple_people, crowd_detected."""

from __future__ import annotations

from sentinel_detect.core.entities.event import EventSeverity, EventType
from sentinel_detect.core.interfaces.event_rule import event_rule_registry
from sentinel_detect.events.base import PersonCountThresholdRule


@event_rule_registry.register("multiple_people")
class MultiplePeopleRule(PersonCountThresholdRule):
    rule_key = "multiple_people"
    event_type = EventType.MULTIPLE_PEOPLE
    severity = EventSeverity.INFO
    default_min_count = 2


@event_rule_registry.register("crowd_detected")
class CrowdDetectedRule(PersonCountThresholdRule):
    rule_key = "crowd_detected"
    event_type = EventType.CROWD_DETECTED
    severity = EventSeverity.WARNING
    default_min_count = 5
