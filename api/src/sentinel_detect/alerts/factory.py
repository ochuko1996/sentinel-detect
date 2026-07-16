"""Composition helper: turns enabled-alert-channel config into live BaseAlertChannel instances."""

from __future__ import annotations

from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.config.settings import AppSettings
from sentinel_detect.core.exceptions import ConfigurationError
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel, alert_channel_registry
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)


def build_enabled_channels(
    settings: AppSettings, resources: AlertResources
) -> dict[str, BaseAlertChannel]:
    """Instantiate every enabled, correctly-configured alert channel.

    A channel that's enabled but missing required config (e.g. webhook
    without a URL, email without SMTP host/creds) is logged and skipped
    rather than crashing startup — same graceful-degradation pattern as
    `build_enabled_detectors`.
    """
    channels: dict[str, BaseAlertChannel] = {}
    for key in settings.enabled_alert_channel_keys():
        try:
            channels[key] = alert_channel_registry.get(key)(settings.alerts[key], resources)
        except ConfigurationError as exc:
            logger.error("alert_channel_unavailable", channel=key, reason=str(exc))
    return channels
