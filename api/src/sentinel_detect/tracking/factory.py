"""Composition helper: builds the configured tracker backend."""

from __future__ import annotations

from sentinel_detect.config.settings import AppSettings
from sentinel_detect.core.interfaces.tracker import BaseTracker, tracker_registry


def build_tracker(settings: AppSettings) -> BaseTracker:
    tracker_cls = tracker_registry.get(settings.tracking.backend)
    return tracker_cls(settings.tracking)
