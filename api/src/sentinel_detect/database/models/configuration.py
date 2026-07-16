"""ORM model for runtime-configurable key/value settings (see
core.entities.configuration for why this is distinct from AppSettings)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_detect.core.entities.configuration import ConfigurationValue
from sentinel_detect.database.base import Base
from sentinel_detect.database.types import UTCDateTime


class ConfigurationRecord(Base):
    __tablename__ = "configurations"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[ConfigurationValue] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
