"""Tests for build_video_source: maps a Camera's source_type to the right
BaseVideoSource, across every branch (image rejected, directory forces
watch=True, everything else goes through the registry uniformly)."""

from __future__ import annotations

import pytest

from sentinel_detect.core.entities.camera import Camera, SourceType
from sentinel_detect.core.exceptions import ConfigurationError
from sentinel_detect.streaming.directory_source import DirectoryVideoSource
from sentinel_detect.streaming.factory import build_video_source
from sentinel_detect.streaming.opencv_source import OpenCVVideoSource


def test_image_source_type_is_rejected_as_unstreamable() -> None:
    camera = Camera(id="cam-1", name="Still", source_type=SourceType.IMAGE, uri="/tmp/x.jpg")

    with pytest.raises(ConfigurationError):
        build_video_source(camera)


def test_directory_source_type_always_watches(tmp_path: object) -> None:
    camera = Camera(id="cam-1", name="Dir", source_type=SourceType.DIRECTORY, uri=str(tmp_path))

    source = build_video_source(camera)

    assert isinstance(source, DirectoryVideoSource)
    assert source._watch is True  # noqa: SLF001 - the whole point of this test
    assert source._camera_id == "cam-1"  # noqa: SLF001


@pytest.mark.parametrize(
    "source_type", [SourceType.RTSP, SourceType.WEBCAM, SourceType.USB, SourceType.IP_CAMERA]
)
def test_other_source_types_resolve_through_the_registry(source_type: SourceType) -> None:
    camera = Camera(id="cam-1", name="Cam", source_type=source_type, uri="rtsp://example.com/1")

    source = build_video_source(camera)

    assert isinstance(source, OpenCVVideoSource)
