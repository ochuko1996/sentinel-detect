"""Domain entities: framework-agnostic data shapes shared across all layers."""

from sentinel_detect.core.entities.alert import Alert, AlertChannelType, AlertStatus
from sentinel_detect.core.entities.camera import Camera, Region, RegionType, SourceType
from sentinel_detect.core.entities.configuration import ConfigurationEntry, ConfigurationValue
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.entities.geometry import BoundingBox, Point, Polygon
from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.entities.tracking import TrackedObject, TrackState
from sentinel_detect.core.entities.user import User, UserRole

__all__ = [
    "Alert",
    "AlertChannelType",
    "AlertStatus",
    "BoundingBox",
    "Camera",
    "ConfigurationEntry",
    "ConfigurationValue",
    "Detection",
    "DetectionClass",
    "Event",
    "EventSeverity",
    "EventType",
    "Frame",
    "Point",
    "Polygon",
    "Region",
    "RegionType",
    "SourceType",
    "TrackedObject",
    "TrackState",
    "User",
    "UserRole",
]
