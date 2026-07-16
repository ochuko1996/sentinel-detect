"""Per-camera WebSocket broadcaster for `WS /ws/stream/{camera_id}`.

Distinct from `alerts/websocket_channel.py::ConnectionManager` (Phase 5),
which broadcasts rule-engine event notifications globally. This broadcasts
every processed frame's tracked-object data (bounding boxes/labels/
confidence) — the spec's "WebSocket streaming" of live detections — scoped
per camera, since a client only wants one camera's feed.
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class StreamBroadcaster:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, camera_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(camera_id, set()).add(websocket)

    def disconnect(self, camera_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(camera_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self._connections[camera_id]

    async def broadcast(self, camera_id: str, message: dict[str, Any]) -> None:
        connections = self._connections.get(camera_id)
        if not connections:
            return
        stale: set[WebSocket] = set()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.add(connection)
        for connection in stale:
            connections.discard(connection)

    def connection_count(self, camera_id: str) -> int:
        return len(self._connections.get(camera_id, ()))
