"""Tests the webhook channel against a real local HTTP server (not a mock),
so we prove httpx actually opens a socket and POSTs valid JSON, not just
that our code calls a mocked client correctly.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.alerts.rest_channel import AlertStore
from sentinel_detect.alerts.webhook_channel import WebhookAlertChannel
from sentinel_detect.alerts.websocket_channel import ConnectionManager
from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.exceptions import AlertDeliveryError, ConfigurationError


class _CapturingHandler(BaseHTTPRequestHandler):
    received: list[dict[str, object]] = []
    response_code = 200

    def do_POST(self) -> None:  # noqa: N802 (stdlib method name)
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        _CapturingHandler.received.append(json.loads(body))
        self.send_response(self.response_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:  # silence test output
        pass


@pytest.fixture
def http_server() -> Iterator[HTTPServer]:
    _CapturingHandler.received = []
    _CapturingHandler.response_code = 200
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()


def _resources() -> AlertResources:
    return AlertResources(connection_manager=ConnectionManager(), alert_store=AlertStore())


def _event() -> Event:
    return Event(
        camera_id="cam-1",
        type=EventType.WEAPON_DETECTED,
        severity=EventSeverity.CRITICAL,
        rule="weapon_detected",
        message="a weapon was detected",
    )


async def test_webhook_channel_posts_real_json_to_a_real_server(http_server: HTTPServer) -> None:
    url = f"http://127.0.0.1:{http_server.server_port}/hook"
    channel = WebhookAlertChannel(AlertChannelSettings(params={"url": url}), _resources())

    await channel.send(_event())

    assert len(_CapturingHandler.received) == 1
    assert _CapturingHandler.received[0]["type"] == "weapon_detected"
    assert _CapturingHandler.received[0]["camera_id"] == "cam-1"


async def test_webhook_channel_raises_alert_delivery_error_on_http_error(
    http_server: HTTPServer,
) -> None:
    _CapturingHandler.response_code = 500
    url = f"http://127.0.0.1:{http_server.server_port}/hook"
    channel = WebhookAlertChannel(AlertChannelSettings(params={"url": url}), _resources())

    with pytest.raises(AlertDeliveryError):
        await channel.send(_event())


async def test_webhook_channel_raises_alert_delivery_error_when_server_unreachable() -> None:
    channel = WebhookAlertChannel(
        AlertChannelSettings(params={"url": "http://127.0.0.1:1/unreachable"}), _resources()
    )

    with pytest.raises(AlertDeliveryError):
        await channel.send(_event())


def test_webhook_channel_requires_a_url() -> None:
    with pytest.raises(ConfigurationError):
        WebhookAlertChannel(AlertChannelSettings(), _resources())
