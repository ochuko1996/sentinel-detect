"""WebSocket alert channel: broadcasts every dispatched alert to connected clients.

`ConnectionManager` is instantiated once in `main.py`'s lifespan and shared
between this channel (which broadcasts) and the `WS /ws/alerts` route
(which registers/unregisters connections) via `app.state`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import WebSocket

from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.alert import AlertChannelType
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel, alert_channel_registry
from sentinel_detect.utils.logging import get_logger

if TYPE_CHECKING:
    from sentinel_detect.alerts.resources import AlertResources

logger = get_logger(__name__)


class ConnectionManager:
    """Tracks currently-connected WebSocket clients and broadcasts to all of them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: set[WebSocket] = set()
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.add(connection)
        for connection in stale:
            self._connections.discard(connection)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


@alert_channel_registry.register("websocket")
class WebSocketAlertChannel(BaseAlertChannel):
    channel_type = AlertChannelType.WEBSOCKET

    def __init__(self, settings: AlertChannelSettings, resources: AlertResources) -> None:
        self._manager = resources.connection_manager

    async def send(self, event: Event) -> None:
        await self._manager.broadcast(event.model_dump(mode="json"))
