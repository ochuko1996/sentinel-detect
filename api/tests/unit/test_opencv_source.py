"""Tests for OpenCVVideoSource against a real synthetic video file (success
path) and real unreachable device/RTSP targets (failure paths) — not mocks.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from sentinel_detect.core.exceptions import VideoSourceError
from sentinel_detect.streaming.opencv_source import OpenCVVideoSource


def _make_synthetic_video(path: Path, num_frames: int = 5) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 32))
    for i in range(num_frames):
        frame = np.full((32, 32, 3), i * 20, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_reads_every_frame_of_a_real_video_file_then_stops(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    _make_synthetic_video(video_path, num_frames=5)

    source = OpenCVVideoSource("cam-1", str(video_path))
    source.open()

    frames = list(iter(source.read, None))

    assert len(frames) == 5
    assert [f.frame_index for f in frames] == [0, 1, 2, 3, 4]
    assert source.read() is None  # exhausted


def test_open_raises_for_a_nonexistent_file() -> None:
    source = OpenCVVideoSource("cam-1", "/no/such/video.mp4")
    with pytest.raises(VideoSourceError):
        source.open()


def test_open_raises_for_an_unavailable_device_index() -> None:
    # A very high device index has no corresponding hardware in any test
    # environment — a real, honest failure path, not simulated.
    source = OpenCVVideoSource("cam-1", "99")
    with pytest.raises(VideoSourceError):
        source.open()


def test_open_raises_for_an_unreachable_rtsp_url() -> None:
    # Port 1 on loopback: nothing listens there, so the real TCP connect
    # genuinely fails — the same kind of failure a real unreachable camera
    # would produce.
    source = OpenCVVideoSource("cam-1", "rtsp://127.0.0.1:1/stream")
    with pytest.raises(VideoSourceError):
        source.open()


def test_read_without_open_raises() -> None:
    source = OpenCVVideoSource("cam-1", "0")
    with pytest.raises(VideoSourceError):
        source.read()


def test_open_is_idempotent(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    _make_synthetic_video(video_path, num_frames=2)

    source = OpenCVVideoSource("cam-1", str(video_path))
    source.open()
    source.open()  # must not raise or reset frame_index

    first = source.read()
    assert first is not None
    assert first.frame_index == 0


def test_close_releases_and_is_open_reflects_state(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    _make_synthetic_video(video_path, num_frames=1)

    source = OpenCVVideoSource("cam-1", str(video_path))
    assert source.is_open is False
    source.open()
    assert source.is_open is True
    source.close()
    assert source.is_open is False


def test_numeric_uri_is_parsed_as_a_device_index_not_a_filename() -> None:
    # "0" must not be interpreted as a relative path "./0" — VideoCapture
    # should receive the integer 0 (a device index), not the string "0".
    # Whether device 0 actually exists is environment-dependent (this
    # sandbox happens to have one; a bare CI container likely won't), so
    # this skips rather than fails when no device is available — but where
    # one *is* available, it genuinely opens it and reads a real frame
    # through the device-index branch, not a mock.
    source = OpenCVVideoSource("cam-1", "0")
    try:
        source.open()
    except VideoSourceError:
        pytest.skip("no video device 0 available in this environment")

    try:
        frame = source.read()
        assert frame is not None
        assert frame.camera_id == "cam-1"
        assert frame.height > 0
        assert frame.width > 0
    finally:
        source.close()
