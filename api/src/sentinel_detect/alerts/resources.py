"""Shared resources multiple alert channels need.

Bundled into one object so every channel's constructor can take the same
`(settings, resources)` signature — channels that don't need a given
resource just ignore it — mirroring `ModelManager` for detectors.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel_detect.alerts.rest_channel import AlertStore
from sentinel_detect.alerts.websocket_channel import ConnectionManager


@dataclass
class AlertResources:
    connection_manager: ConnectionManager
    alert_store: AlertStore
