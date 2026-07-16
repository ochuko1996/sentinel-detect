"""The alert engine: fans events out to every active alert channel."""

from __future__ import annotations

from datetime import UTC, datetime

from sentinel_detect.core.entities.alert import Alert, AlertStatus
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.exceptions import AlertDeliveryError
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)


class AlertEngine:
    def __init__(self, channels: dict[str, BaseAlertChannel]) -> None:
        self._channels = channels

    async def dispatch(self, events: list[Event]) -> list[Alert]:
        """Send every event through every active channel, recording the outcome."""
        alerts: list[Alert] = []
        for event in events:
            for channel in self._channels.values():
                try:
                    await channel.send(event)
                except AlertDeliveryError as exc:
                    logger.error(
                        "alert_delivery_failed",
                        channel=channel.channel_type.value,
                        event_type=event.type.value,
                        error=str(exc),
                    )
                    alerts.append(
                        Alert(
                            event=event,
                            channel=channel.channel_type,
                            status=AlertStatus.FAILED,
                            error=str(exc),
                        )
                    )
                else:
                    alerts.append(
                        Alert(
                            event=event,
                            channel=channel.channel_type,
                            status=AlertStatus.SENT,
                            delivered_at=datetime.now(UTC),
                        )
                    )
        return alerts

    def active_channel_keys(self) -> list[str]:
        return sorted(self._channels)
