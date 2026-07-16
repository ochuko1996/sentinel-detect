"""Request/response schemas for the video tracking/event endpoint."""

from __future__ import annotations

from pydantic import BaseModel

from sentinel_detect.api.schemas.events import EventSummary
from sentinel_detect.core.entities.geometry import BoundingBox


class TrackSummary(BaseModel):
    track_id: int
    label: str
    first_seen_frame: int
    last_seen_frame: int
    frames_tracked: int
    last_bbox: BoundingBox
    last_confidence: float


class DetectVideoResponse(BaseModel):
    camera_id: str
    frames_processed: int
    active_detectors: list[str]
    active_rules: list[str]
    active_alert_channels: list[str]
    tracks: list[TrackSummary]
    events: list[EventSummary]
    detections_stored: int
    events_stored: int
    alerts_stored: int
