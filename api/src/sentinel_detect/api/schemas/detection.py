"""Request/response schemas for the detection endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from sentinel_detect.core.entities.detection import Detection


class DetectImageResponse(BaseModel):
    camera_id: str
    frame_width: int
    frame_height: int
    detections: list[Detection]
    active_detectors: list[str]
