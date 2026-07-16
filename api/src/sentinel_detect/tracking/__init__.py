"""BaseTracker implementations. ByteTrack today; DeepSORT is a plausible
future addition needing only a new `tracker_registry` entry.

Importing this package registers every built-in tracker backend as a side
effect — required before `build_tracker` can resolve one by key.
"""

from sentinel_detect.tracking import byte_track  # noqa: F401
from sentinel_detect.tracking.factory import build_tracker

__all__ = ["build_tracker"]

