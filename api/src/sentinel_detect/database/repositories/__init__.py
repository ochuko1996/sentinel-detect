"""Concrete `Repository[T, ID]` implementations, one per persisted entity."""

from sentinel_detect.database.repositories.alert_repository import AlertRepository
from sentinel_detect.database.repositories.camera_repository import CameraRepository
from sentinel_detect.database.repositories.configuration_repository import (
    ConfigurationRepository,
)
from sentinel_detect.database.repositories.detection_repository import DetectionRepository
from sentinel_detect.database.repositories.event_repository import EventRepository
from sentinel_detect.database.repositories.user_repository import UserRepository

__all__ = [
    "AlertRepository",
    "CameraRepository",
    "ConfigurationRepository",
    "DetectionRepository",
    "EventRepository",
    "UserRepository",
]
