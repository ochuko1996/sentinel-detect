"""Tests for DirectoryVideoSource against a real temp directory with real
image files (not mocked) — both batch (watch=False) and monitoring
(watch=True) modes.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from sentinel_detect.core.exceptions import VideoSourceError
from sentinel_detect.streaming.directory_source import DirectoryVideoSource


def _write_image(path: Path, fill: int) -> None:
    image = np.full((16, 16, 3), fill, dtype=np.uint8)
    cv2.imwrite(str(path), image)


def test_open_rejects_a_path_that_is_not_a_directory(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("hello")
    source = DirectoryVideoSource("cam-1", str(not_a_dir))

    with pytest.raises(VideoSourceError):
        source.open()


def test_read_without_open_raises() -> None:
    source = DirectoryVideoSource("cam-1", "/tmp")
    with pytest.raises(VideoSourceError):
        source.read()


def test_batch_mode_drains_existing_files_in_order_then_stops(tmp_path: Path) -> None:
    _write_image(tmp_path / "b.jpg", 50)
    _write_image(tmp_path / "a.jpg", 10)
    _write_image(tmp_path / "c.jpg", 90)

    source = DirectoryVideoSource("cam-1", str(tmp_path), watch=False)
    source.open()

    frames = list(iter(source.read, None))

    assert len(frames) == 3
    # Sorted by filename: a.jpg, b.jpg, c.jpg
    assert [int(f.image[0, 0, 0]) for f in frames] == [10, 50, 90]
    assert [f.frame_index for f in frames] == [0, 1, 2]


def test_batch_mode_ignores_non_image_files(tmp_path: Path) -> None:
    _write_image(tmp_path / "a.jpg", 10)
    (tmp_path / "readme.txt").write_text("not an image")

    source = DirectoryVideoSource("cam-1", str(tmp_path), watch=False)
    source.open()

    frames = list(iter(source.read, None))

    assert len(frames) == 1


def test_batch_mode_skips_a_corrupt_image_file_and_keeps_looking(tmp_path: Path) -> None:
    (tmp_path / "corrupt.jpg").write_bytes(b"not actually a jpeg")
    _write_image(tmp_path / "z_good.jpg", 10)  # sorts after "corrupt.jpg"

    source = DirectoryVideoSource("cam-1", str(tmp_path), watch=False)
    source.open()

    frames = list(iter(source.read, None))

    assert len(frames) == 1
    assert int(frames[0].image[0, 0, 0]) == 10


def test_watch_mode_picks_up_a_file_added_after_open(tmp_path: Path) -> None:
    _write_image(tmp_path / "a.jpg", 10)
    source = DirectoryVideoSource("cam-1", str(tmp_path), watch=True, poll_seconds=0.05)
    source.open()

    first = source.read()
    assert first is not None

    def _add_second_file() -> None:
        time.sleep(0.1)
        _write_image(tmp_path / "b.jpg", 20)

    threading.Thread(target=_add_second_file, daemon=True).start()
    second = source.read()

    assert second is not None
    assert int(second.image[0, 0, 0]) == 20
    source.close()


def test_close_then_reopen_does_not_reread_already_seen_files(tmp_path: Path) -> None:
    _write_image(tmp_path / "a.jpg", 10)
    source = DirectoryVideoSource("cam-1", str(tmp_path), watch=False)
    source.open()
    first_pass = list(iter(source.read, None))
    source.close()

    source.open()
    second_pass_frame = source.read()

    assert len(first_pass) == 1
    assert second_pass_frame is None  # already seen; batch mode has nothing new


def test_is_open_reflects_state() -> None:
    source = DirectoryVideoSource("cam-1", "/tmp")
    assert source.is_open is False
    source.open()
    assert source.is_open is True
    source.close()
    assert source.is_open is False
