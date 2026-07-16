"""ORM model for rule-engine events."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_detect.database.base import Base
from sentinel_detect.database.types import UTCDateTime


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_camera_timestamp", "camera_id", "timestamp"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    camera_id: Mapped[str] = mapped_column(index=True)
    type: Mapped[str]
    severity: Mapped[str]
    rule: Mapped[str]
    track_ids: Mapped[list[int]] = mapped_column(JSON)
    region_id: Mapped[str | None]
    message: Mapped[str]
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
