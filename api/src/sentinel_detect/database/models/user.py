"""ORM model for user accounts (persistence only — Phase 7 wires auth on top)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from sentinel_detect.database.base import Base
from sentinel_detect.database.types import UTCDateTime


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
    role: Mapped[str]
    is_active: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
