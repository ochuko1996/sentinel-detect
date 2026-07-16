"""Request/response schemas for live streaming endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StartStreamRequest(BaseModel):
    camera_id: str


class StreamStatusResponse(BaseModel):
    camera_id: str
    started_at: datetime
    frames_processed: int
    last_error: str | None
