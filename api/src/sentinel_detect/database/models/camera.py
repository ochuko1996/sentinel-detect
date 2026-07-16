"""ORM model for configured camera/input sources.

Regions (ROIs) are stored as a JSON blob rather than normalized into
separate tables — there's no ROI CRUD yet (Phase 7), and a `Region` is a
small, always-read-as-a-whole nested structure (polygon/line + metadata),
so normalizing it now would be speculative complexity with no current
reader to justify it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_detect.database.base import Base


class CameraRecord(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    source_type: Mapped[str]
    uri: Mapped[str]
    enabled: Mapped[bool]
    enabled_detectors: Mapped[list[str]] = mapped_column(JSON)
    regions: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    frame_rate_limit: Mapped[float | None]
    inference_width: Mapped[int]
    inference_height: Mapped[int]
