"""Ports: abstract interfaces that infrastructure adapters implement."""

from sentinel_detect.core.interfaces.alert_channel import (
    BaseAlertChannel,
    alert_channel_registry,
)
from sentinel_detect.core.interfaces.detector import BaseDetector, detector_registry
from sentinel_detect.core.interfaces.event_rule import (
    BaseEventRule,
    EventContext,
    event_rule_registry,
)
from sentinel_detect.core.interfaces.model import BaseInferenceModel, RawPrediction
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.core.interfaces.storage import (
    BaseStorageBackend,
    storage_backend_registry,
)
from sentinel_detect.core.interfaces.tracker import BaseTracker, tracker_registry
from sentinel_detect.core.interfaces.video_source import (
    BaseVideoSource,
    video_source_registry,
)

__all__ = [
    "BaseAlertChannel",
    "BaseDetector",
    "BaseEventRule",
    "BaseInferenceModel",
    "BaseStorageBackend",
    "BaseTracker",
    "BaseVideoSource",
    "EventContext",
    "RawPrediction",
    "Repository",
    "alert_channel_registry",
    "detector_registry",
    "event_rule_registry",
    "storage_backend_registry",
    "tracker_registry",
    "video_source_registry",
]
