"""Tests the email channel against a minimal real local SMTP server (not a
mock of smtplib), so we prove smtplib actually opens a socket and speaks
the protocol correctly, not just that our code calls a mocked client.

The stub server implements just enough of RFC 5321 for smtplib's basic
EHLO/MAIL/RCPT/DATA/QUIT flow with no STARTTLS/AUTH — tests configure the
channel with use_tls=false and no username accordingly.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest

from sentinel_detect.alerts.email_channel import SmtpEmailAlertChannel
from sentinel_detect.alerts.resources import AlertResources
from sentinel_detect.alerts.rest_channel import AlertStore
from sentinel_detect.alerts.websocket_channel import ConnectionManager
from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.exceptions import AlertDeliveryError, ConfigurationError


class _FakeSmtpServer:
    """A bare-bones SMTP server: EHLO/MAIL/RCPT/DATA/QUIT, no STARTTLS/AUTH."""

    def __init__(self) -> None:
        self.received_messages: list[str] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self._sock.settimeout(0.5)
        self.port: int = self._sock.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break  # socket closed by stop() while accept() was blocked
            with conn:
                self._handle(conn)

    def _handle(self, conn: socket.socket) -> None:
        f = conn.makefile("rwb")

        def send(line: str) -> None:
            f.write((line + "\r\n").encode())
            f.flush()

        send("220 localhost ESMTP")
        data_mode = False
        buffer: list[str] = []
        while True:
            raw = f.readline()
            if not raw:
                break
            line = raw.decode(errors="replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    self.received_messages.append("\n".join(buffer))
                    buffer = []
                    data_mode = False
                    send("250 OK")
                else:
                    buffer.append(line)
                continue

            command = line.split()[0].upper() if line else ""
            if command in ("EHLO", "HELO"):
                send("250 localhost")
            elif command in ("MAIL", "RCPT"):
                send("250 OK")
            elif command == "DATA":
                send("354 End data with <CR><LF>.<CR><LF>")
                data_mode = True
            elif command == "QUIT":
                send("221 Bye")
                break
            else:
                send("500 unrecognized command")

    def stop(self) -> None:
        self._running = False
        self._sock.close()
        self._thread.join()


@pytest.fixture
def smtp_server() -> Iterator[_FakeSmtpServer]:
    server = _FakeSmtpServer()
    try:
        yield server
    finally:
        server.stop()


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


def _settings(port: int) -> AlertChannelSettings:
    return AlertChannelSettings(
        params={
            "smtp_host": "127.0.0.1",
            "smtp_port": str(port),
            "use_tls": "false",
            "from_addr": "alerts@sentinel.local",
            "to_addrs": "ops@sentinel.local",
        }
    )


async def test_email_channel_sends_a_real_message_over_a_real_socket(
    smtp_server: _FakeSmtpServer,
) -> None:
    channel = SmtpEmailAlertChannel(_settings(smtp_server.port), _resources())

    await channel.send(_event())

    assert len(smtp_server.received_messages) == 1
    message = smtp_server.received_messages[0]
    assert "weapon_detected" in message
    assert "alerts@sentinel.local" in message
    assert "ops@sentinel.local" in message


async def test_email_channel_raises_alert_delivery_error_when_server_unreachable() -> None:
    settings = AlertChannelSettings(
        params={
            "smtp_host": "127.0.0.1",
            "smtp_port": "1",
            "use_tls": "false",
            "from_addr": "alerts@sentinel.local",
            "to_addrs": "ops@sentinel.local",
        }
    )
    channel = SmtpEmailAlertChannel(settings, _resources())

    with pytest.raises(AlertDeliveryError):
        await channel.send(_event())


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"smtp_host": "127.0.0.1"},
        {"smtp_host": "127.0.0.1", "from_addr": "a@b.com"},
    ],
)
def test_email_channel_requires_host_from_and_to(params: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        SmtpEmailAlertChannel(AlertChannelSettings(params=params), _resources())
