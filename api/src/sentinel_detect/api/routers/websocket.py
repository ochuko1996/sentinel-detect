"""WS /ws/alerts — live stream of every alert as it's dispatched.
WS /ws/stream/{camera_id} — live stream of a specific camera's processed frames.

`/ws/alerts` clients receive a JSON-serialized `Event` (see
`Event.model_dump(mode="json")`) each time `AlertEngine.dispatch()` sends
through the `websocket` channel. `/ws/stream/{camera_id}` clients receive
one message per frame `StreamManager` processes for that camera: bounding
boxes/labels/confidence for every currently tracked object (see
`streaming/broadcaster.py::StreamBroadcaster`) — distinct from `/ws/alerts`,
which only carries rule-engine event notifications, not raw per-frame
detections. Both connections are otherwise passive: the server doesn't
expect the client to send anything, it just needs the receive loop to
detect disconnection.

Both managers are read directly off `websocket.app.state` rather than
through a `Depends()`-based dependency: FastAPI's dependency injection for
WebSocket routes requires a dependency callable to take a `websocket:
WebSocket` parameter, not `request: Request` — there is no HTTP request in
a WebSocket connection, so a `Request`-based dependency (like the one used
for HTTP routes) fails at runtime.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sentinel_detect.alerts.websocket_channel import ConnectionManager
from sentinel_detect.streaming import StreamBroadcaster

router = APIRouter(tags=["alerts"])


@router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket) -> None:
    manager: ConnectionManager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/stream/{camera_id}")
async def stream_websocket(websocket: WebSocket, camera_id: str) -> None:
    broadcaster: StreamBroadcaster = websocket.app.state.stream_broadcaster
    await broadcaster.connect(camera_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(camera_id, websocket)
