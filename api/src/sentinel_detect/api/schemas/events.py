"""Shared event response schema, used by both `/detect/video` and `/alerts`."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from sentinel_detect.core.entities.event import Event


class EventSummary(BaseModel):
    type: str
    severity: str
    rule: str
    track_ids: tuple[int, ...]
    region_id: str | None
    message: str
    timestamp: datetime

    @classmethod
    def from_event(cls, event: Event) -> EventSummary:
        return cls(
            type=event.type.value,
            severity=event.severity.value,
            rule=event.rule,
            track_ids=event.track_ids,
            region_id=event.region_id,
            message=event.message,
            timestamp=event.timestamp,
        )
