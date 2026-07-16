from typing import Any

from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.alerts.rest_channel import AlertStore
from sentinel_detect.alerts.websocket_channel import ConnectionManager, WebSocketAlertChannel
from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType


class _FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.accepted = False
        self.received: list[dict[str, Any]] = []
        self._fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        if self._fail:
            raise RuntimeError("connection closed")
        self.received.append(message)


def _event() -> Event:
    return Event(
        camera_id="cam-1",
        type=EventType.PERSON_DETECTED,
        severity=EventSeverity.INFO,
        rule="person_detected",
        message="a person was detected",
    )


async def test_connect_accepts_and_registers_the_socket() -> None:
    manager = ConnectionManager()
    ws = _FakeWebSocket()

    await manager.connect(ws)

    assert ws.accepted is True
    assert manager.connection_count == 1


async def test_broadcast_sends_to_every_connected_client() -> None:
    manager = ConnectionManager()
    ws_a, ws_b = _FakeWebSocket(), _FakeWebSocket()
    await manager.connect(ws_a)
    await manager.connect(ws_b)

    await manager.broadcast({"hello": "world"})

    assert ws_a.received == [{"hello": "world"}]
    assert ws_b.received == [{"hello": "world"}]


async def test_broadcast_drops_connections_that_raise() -> None:
    manager = ConnectionManager()
    dead = _FakeWebSocket(fail=True)
    alive = _FakeWebSocket()
    await manager.connect(dead)
    await manager.connect(alive)

    await manager.broadcast({"hello": "world"})

    assert manager.connection_count == 1
    assert alive.received == [{"hello": "world"}]


def test_disconnect_removes_the_socket() -> None:
    manager = ConnectionManager()
    ws = _FakeWebSocket()
    manager._connections.add(ws)  # type: ignore[arg-type]

    manager.disconnect(ws)  # type: ignore[arg-type]

    assert manager.connection_count == 0


async def test_websocket_alert_channel_broadcasts_the_event_payload() -> None:
    manager = ConnectionManager()
    ws = _FakeWebSocket()
    await manager.connect(ws)
    resources = AlertResources(connection_manager=manager, alert_store=AlertStore())
    channel = WebSocketAlertChannel(AlertChannelSettings(), resources)
    event = _event()

    await channel.send(event)

    assert len(ws.received) == 1
    assert ws.received[0]["type"] == "person_detected"
    assert ws.received[0]["camera_id"] == "cam-1"
