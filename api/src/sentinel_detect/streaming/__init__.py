"""Input source implementations and the live streaming/WebSocket pipeline.

Importing this package registers every built-in video source as a side
effect — required before `build_video_source` can resolve one by
`SourceType`.
"""

from sentinel_detect.streaming import directory_source, opencv_source  # noqa: F401
from sentinel_detect.streaming.broadcaster import StreamBroadcaster
from sentinel_detect.streaming.factory import build_video_source
from sentinel_detect.streaming.stream_manager import StreamManager, StreamStatus

__all__ = [
    "StreamBroadcaster",
    "StreamManager",
    "StreamStatus",
    "build_video_source",
]
