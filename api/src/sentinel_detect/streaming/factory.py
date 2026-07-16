"""Composition helper: builds the right BaseVideoSource for a Camera's configured source_type."""

from __future__ import annotations

from sentinel_detect.core.entities.camera import Camera, SourceType
from sentinel_detect.core.exceptions import ConfigurationError
from sentinel_detect.core.interfaces.video_source import BaseVideoSource, video_source_registry


def build_video_source(camera: Camera) -> BaseVideoSource:
    if camera.source_type is SourceType.IMAGE:
        raise ConfigurationError(
            "source_type 'image' is a single still image, not a streamable source "
            "— use POST /detect/image instead of live streaming"
        )
    if camera.source_type is SourceType.DIRECTORY:
        source = video_source_registry.get("directory")
        return source(camera_id=camera.id, directory=camera.uri, watch=True)

    source = video_source_registry.get(camera.source_type.value)
    return source(camera_id=camera.id, uri=camera.uri)
