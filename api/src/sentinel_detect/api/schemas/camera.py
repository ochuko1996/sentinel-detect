"""Request schemas for camera CRUD.

Responses use `core.entities.camera.Camera` directly (same precedent as
`Detection`/`TrackedObject` elsewhere) rather than a parallel response
schema that would just duplicate its fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sentinel_detect.core.entities.camera import Region, SourceType


class CameraCreateRequest(BaseModel):
    id: str
    name: str
    source_type: SourceType
    uri: str
    enabled: bool = True
    enabled_detectors: tuple[str, ...] = Field(default_factory=tuple)
    regions: tuple[Region, ...] = Field(default_factory=tuple)
    frame_rate_limit: float | None = Field(default=None, gt=0)
    inference_size: tuple[int, int] = (640, 640)


class CameraUpdateRequest(BaseModel):
    """All fields optional — only fields actually set in the request are changed."""

    name: str | None = None
    source_type: SourceType | None = None
    uri: str | None = None
    enabled: bool | None = None
    enabled_detectors: tuple[str, ...] | None = None
    regions: tuple[Region, ...] | None = None
    frame_rate_limit: float | None = Field(default=None, gt=0)
    inference_size: tuple[int, int] | None = None
