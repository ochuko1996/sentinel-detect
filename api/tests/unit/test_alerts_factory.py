"""Tests for build_enabled_channels: graceful degradation when an enabled
channel is missing required config, same pattern as build_enabled_detectors."""

from __future__ import annotations

from sentinel_detect.alerts.factory import build_enabled_channels
from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.alerts.rest_channel import AlertStore
from sentinel_detect.alerts.websocket_channel import ConnectionManager
from sentinel_detect.config.settings import AppSettings


def _resources() -> AlertResources:
    return AlertResources(connection_manager=ConnectionManager(), alert_store=AlertStore())


def test_default_settings_build_rest_and_websocket_channels() -> None:
    settings = AppSettings(_env_file=None)

    channels = build_enabled_channels(settings, _resources())

    assert set(channels) == {"rest", "websocket"}


def test_an_enabled_channel_missing_required_config_is_skipped_not_raised() -> None:
    settings = AppSettings(_env_file=None)
    settings.alerts["webhook"].enabled = True  # no params.url set

    channels = build_enabled_channels(settings, _resources())

    assert "webhook" not in channels
    assert {"rest", "websocket"} <= set(channels)
