"""Alert channel port (Phase 5: REST/WebSocket/email/webhook/... delivery)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel_detect.core.entities.alert import AlertChannelType
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.registry import Registry


class BaseAlertChannel(ABC):
    """Port for delivering an `Event` through one notification mechanism."""

    channel_type: AlertChannelType

    @abstractmethod
    async def send(self, event: Event) -> None:
        """Deliver `event`. Raise `AlertDeliveryError` on failure."""


alert_channel_registry: Registry[BaseAlertChannel] = Registry("alert_channel")
