"""The rule engine: fans an EventContext out to every active rule."""

from __future__ import annotations

from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.interfaces.event_rule import BaseEventRule, EventContext


class EventEngine:
    def __init__(self, rules: dict[str, BaseEventRule]) -> None:
        self._rules = rules

    def evaluate(self, context: EventContext) -> list[Event]:
        events: list[Event] = []
        for rule in self._rules.values():
            events.extend(rule.evaluate(context))
        return events

    def active_rule_keys(self) -> list[str]:
        return sorted(self._rules)
