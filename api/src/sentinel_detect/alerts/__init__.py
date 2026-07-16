"""BaseAlertChannel implementations: REST, WebSocket, webhook, email.

SMS/push/Slack/Teams remain `AlertChannelType` enum entries only — no
implementation exists yet; adding one is a new `alert_channel_registry`
entry, no core code changes.

Importing this package registers every built-in channel as a side effect —
required before `build_enabled_channels` can resolve one by key.
"""

from sentinel_detect.alerts import (  # noqa: F401
    email_channel,
    rest_channel,
    webhook_channel,
    websocket_channel,
)
from sentinel_detect.alerts.factory import build_enabled_channels
from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.alerts.rest_channel import AlertStore
from sentinel_detect.alerts.websocket_channel import ConnectionManager

__all__ = [
    "AlertResources",
    "AlertStore",
    "ConnectionManager",
    "build_enabled_channels",
]

