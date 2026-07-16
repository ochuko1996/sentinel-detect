"""Alert entities produced by the alert engine (Phase 5)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from sentinel_detect.core.entities.event import Event


class AlertChannelType(StrEnum):
    """Delivery mechanisms an alert can be routed through."""

    REST = "rest"
    WEBSOCKET = "websocket"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    PUSH = "push"
    SLACK = "slack"
    TEAMS = "teams"


class AlertStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Alert(BaseModel, frozen=True):
    """A dispatch of an `Event` through one alert channel."""

    id: UUID = Field(default_factory=uuid4)
    event: Event
    channel: AlertChannelType
    status: AlertStatus = AlertStatus.PENDING
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    delivered_at: datetime | None = None
