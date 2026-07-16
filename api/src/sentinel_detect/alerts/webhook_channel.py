"""Webhook alert channel: POSTs the event as JSON to a configured URL."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.alert import AlertChannelType
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.exceptions import AlertDeliveryError, ConfigurationError
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel, alert_channel_registry

if TYPE_CHECKING:
    from sentinel_detect.alerts.resources import AlertResources

_DEFAULT_TIMEOUT_SECONDS = 5.0


@alert_channel_registry.register("webhook")
class WebhookAlertChannel(BaseAlertChannel):
    channel_type = AlertChannelType.WEBHOOK

    def __init__(self, settings: AlertChannelSettings, resources: AlertResources) -> None:
        url = settings.params.get("url")
        if not url:
            raise ConfigurationError(
                "webhook alert channel is enabled but params.url is not set "
                "(SENTINEL_ALERTS__WEBHOOK__PARAMS__URL=https://...)"
            )
        self._url = url
        self._timeout = float(settings.params.get("timeout_seconds", str(_DEFAULT_TIMEOUT_SECONDS)))

    async def send(self, event: Event) -> None:
        payload = event.model_dump(mode="json")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AlertDeliveryError(f"webhook delivery to '{self._url}' failed: {exc}") from exc
