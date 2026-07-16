"""Composition helper: turns enabled-event-rule config into live BaseEventRule instances."""

from __future__ import annotations

from sentinel_detect.config.settings import AppSettings
from sentinel_detect.core.interfaces.event_rule import BaseEventRule, event_rule_registry


def build_enabled_rules(settings: AppSettings) -> dict[str, BaseEventRule]:
    return {
        key: event_rule_registry.get(key)(settings.events[key])
        for key in settings.enabled_event_rule_keys()
    }
