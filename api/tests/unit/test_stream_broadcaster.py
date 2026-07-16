"""Tests for StreamBroadcaster: per-camera WebSocket connection registry and
fan-out, including dead-connection cleanup on a failed send.

Uses a minimal fake WebSocket (async accept()/send_json()) rather than a
real ASGI connection — StreamBroadcaster only ever calls these two methods,
so a fake exercising the exact contract is simpler and just as genuine here
as standing up a real socket would be (contrast with the video sources,
where the actual I/O behavior itself was what needed proving).
"""

from __future__ import annotations

from sentinel_detect.streaming.broadcaster import StreamBroadcaster


class _FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict[str, object]] = []
        self._fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        if self._fail_send:
            raise RuntimeError("connection closed")
        self.sent.append(message)


async def test_connect_accepts_and_registers_the_connection() -> None:
    broadcaster = StreamBroadcaster()
    ws = _FakeWebSocket()

    await broadcaster.connect("cam-1", ws)  # type: ignore[arg-type]

    assert ws.accepted is True
    assert broadcaster.connection_count("cam-1") == 1


def test_connection_count_is_zero_for_an_unknown_camera() -> None:
    broadcaster = StreamBroadcaster()

    assert broadcaster.connection_count("never-connected") == 0


async def test_disconnect_removes_a_registered_connection() -> None:
    broadcaster = StreamBroadcaster()
    ws = _FakeWebSocket()
    await broadcaster.connect("cam-1", ws)  # type: ignore[arg-type]

    broadcaster.disconnect("cam-1", ws)  # type: ignore[arg-type]

    assert broadcaster.connection_count("cam-1") == 0


def test_disconnect_is_a_noop_for_a_camera_with_no_connections() -> None:
    broadcaster = StreamBroadcaster()

    broadcaster.disconnect("never-connected", _FakeWebSocket())  # type: ignore[arg-type]


async def test_broadcast_delivers_to_every_connected_client() -> None:
    broadcaster = StreamBroadcaster()
    first = _FakeWebSocket()
    second = _FakeWebSocket()
    await broadcaster.connect("cam-1", first)  # type: ignore[arg-type]
    await broadcaster.connect("cam-1", second)  # type: ignore[arg-type]

    await broadcaster.broadcast("cam-1", {"frame_index": 0})

    assert first.sent == [{"frame_index": 0}]
    assert second.sent == [{"frame_index": 0}]


async def test_broadcast_to_a_camera_with_no_connections_is_a_noop() -> None:
    broadcaster = StreamBroadcaster()

    await broadcaster.broadcast("never-connected", {"frame_index": 0})  # must not raise


async def test_broadcast_drops_a_connection_whose_send_fails() -> None:
    broadcaster = StreamBroadcaster()
    healthy = _FakeWebSocket()
    dead = _FakeWebSocket(fail_send=True)
    await broadcaster.connect("cam-1", healthy)  # type: ignore[arg-type]
    await broadcaster.connect("cam-1", dead)  # type: ignore[arg-type]

    await broadcaster.broadcast("cam-1", {"frame_index": 0})

    assert healthy.sent == [{"frame_index": 0}]
    assert broadcaster.connection_count("cam-1") == 1  # the dead one was pruned
