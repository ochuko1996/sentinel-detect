"""REST alert channel: a bounded in-memory store that `GET /alerts` reads from.

There's no database yet (Phase 6), so this is genuinely in-memory and does
not survive a restart — but it's real, working storage, not a stub. Phase 6
can back this with persistence without changing the channel's contract.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.alert import AlertChannelType
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel, alert_channel_registry

if TYPE_CHECKING:
    from sentinel_detect.alerts.resources import AlertResources

_DEFAULT_MAX_STORED = 500


class AlertStore:
    """Bounded most-recent-first buffer of delivered events."""

    def __init__(self, max_size: int = _DEFAULT_MAX_STORED) -> None:
        self._events: deque[Event] = deque(maxlen=max_size)

    def add(self, event: Event) -> None:
        self._events.append(event)

    def recent(self, limit: int = 100) -> list[Event]:
        """Most-recently-added first, capped at `limit`."""
        return list(reversed(self._events))[:limit]

    def __len__(self) -> int:
        return len(self._events)


@alert_channel_registry.register("rest")
class RestAlertChannel(BaseAlertChannel):
    channel_type = AlertChannelType.REST

    def __init__(self, settings: AlertChannelSettings, resources: AlertResources) -> None:
        self._store = resources.alert_store

    async def send(self, event: Event) -> None:
        self._store.add(event)
