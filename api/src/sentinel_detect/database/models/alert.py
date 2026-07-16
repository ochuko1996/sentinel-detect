"""ORM model for alert dispatch attempts — this platform's audit-trail /
"logs" table (see docs/architecture.md for why `Alert` records serve that
role instead of a separate synthetic logs table)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_detect.database.base import Base
from sentinel_detect.database.types import UTCDateTime


class AlertRecord(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_event_id", "event_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    channel: Mapped[str]
    status: Mapped[str]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
