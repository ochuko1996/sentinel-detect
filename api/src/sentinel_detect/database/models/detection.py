"""ORM model for raw per-frame, per-detector detections."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_detect.database.base import Base
from sentinel_detect.database.types import UTCDateTime


class DetectionRecord(Base):
    __tablename__ = "detections"
    __table_args__ = (Index("ix_detections_camera_timestamp", "camera_id", "timestamp"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    camera_id: Mapped[str] = mapped_column(index=True)
    detector: Mapped[str]
    label: Mapped[str]
    confidence: Mapped[float]
    bbox_x1: Mapped[float]
    bbox_y1: Mapped[float]
    bbox_x2: Mapped[float]
    bbox_y2: Mapped[float]
    frame_width: Mapped[int]
    frame_height: Mapped[int]
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
