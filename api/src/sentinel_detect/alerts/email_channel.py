"""SMTP email alert channel.

A genuine implementation via stdlib `smtplib`/`email` — not a stub — but
disabled by default, since actually delivering mail needs real SMTP
credentials nobody can supply in this environment (matching the spec's own
"Email (interface)" framing, and the same honesty as the weapon/fire/PPE
detectors needing real weights). `smtplib` is blocking, so the actual send
runs via `asyncio.to_thread` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING

from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.alert import AlertChannelType
from sentinel_detect.core.entities.event import Event
from sentinel_detect.core.exceptions import AlertDeliveryError, ConfigurationError
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel, alert_channel_registry

if TYPE_CHECKING:
    from sentinel_detect.alerts.resources import AlertResources

_DEFAULT_SMTP_PORT = 587
_DEFAULT_TIMEOUT_SECONDS = 10.0


@alert_channel_registry.register("email")
class SmtpEmailAlertChannel(BaseAlertChannel):
    channel_type = AlertChannelType.EMAIL

    def __init__(self, settings: AlertChannelSettings, resources: AlertResources) -> None:
        host = settings.params.get("smtp_host")
        from_addr = settings.params.get("from_addr")
        to_addrs = settings.params.get("to_addrs")
        if not host or not from_addr or not to_addrs:
            raise ConfigurationError(
                "email alert channel is enabled but requires params.smtp_host, "
                "params.from_addr, and params.to_addrs to be set"
            )
        self._host = host
        self._port = int(settings.params.get("smtp_port", str(_DEFAULT_SMTP_PORT)))
        self._use_tls = settings.params.get("use_tls", "true").lower() == "true"
        self._username = settings.params.get("username", "")
        self._password = settings.params.get("password", "")
        self._from_addr = from_addr
        self._to_addrs = [addr.strip() for addr in to_addrs.split(",") if addr.strip()]

    async def send(self, event: Event) -> None:
        message = EmailMessage()
        message["Subject"] = f"SENTINEL Detect: {event.type.value} ({event.severity.value})"
        message["From"] = self._from_addr
        message["To"] = ", ".join(self._to_addrs)
        message.set_content(
            f"{event.message}\n\n"
            f"Camera: {event.camera_id}\n"
            f"Rule: {event.rule}\n"
            f"Tracks: {list(event.track_ids)}\n"
            f"Time: {event.timestamp.isoformat()}"
        )

        try:
            await asyncio.to_thread(self._send_sync, message)
        except (smtplib.SMTPException, OSError) as exc:
            raise AlertDeliveryError(
                f"failed to send email via {self._host}:{self._port}: {exc}"
            ) from exc

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=_DEFAULT_TIMEOUT_SECONDS) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
