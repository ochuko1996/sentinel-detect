"""BaseVideoSource that watches a directory for image files.

Serves two of the spec's input modes with one implementation, distinguished
by `watch`:

- **Batch image processing** (`watch=False`): drains whatever image files
  already exist in the directory, then `read()` returns `None` — a bounded,
  one-shot pass, same shape as processing an uploaded video's frames.
- **Directory monitoring** (`watch=True`): the same drain, but polls
  indefinitely for new files instead of stopping — used for a live stream
  sourced from a directory (e.g. a folder a separate process drops
  snapshots into).

Polls the directory rather than using OS-level file-watching (inotify
etc.) — simpler, portable, and fine at the interval a security-camera
directory realistically needs (new files arrive on the order of seconds,
not milliseconds).
"""

from __future__ import annotations

import threading
from pathlib import Path

import cv2

from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.exceptions import VideoSourceError
from sentinel_detect.core.interfaces.video_source import BaseVideoSource, video_source_registry

_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp"})
_DEFAULT_POLL_SECONDS = 1.0


@video_source_registry.register("directory")
class DirectoryVideoSource(BaseVideoSource):
    def __init__(
        self,
        camera_id: str,
        directory: str,
        *,
        watch: bool = False,
        poll_seconds: float = _DEFAULT_POLL_SECONDS,
    ) -> None:
        self._camera_id = camera_id
        self._directory = Path(directory)
        self._watch = watch
        self._poll_seconds = poll_seconds
        self._seen: set[str] = set()
        self._frame_index = 0
        self._open = False
        # A `threading.Event` rather than `time.sleep` for the poll wait: it
        # lets `close()` — called from the asyncio loop thread while `read()`
        # is blocked on a worker thread — wake the wait immediately instead
        # of leaving it to sleep out a full poll interval (or, in watch
        # mode against an empty directory, forever).
        self._stop_event = threading.Event()

    def open(self) -> None:
        if not self._directory.is_dir():
            raise VideoSourceError(f"'{self._directory}' is not a directory")
        self._stop_event.clear()
        self._open = True

    def read(self) -> Frame | None:
        if not self._open:
            raise VideoSourceError("source not open; call open() first")

        while True:
            if self._stop_event.is_set():
                return None

            candidates = sorted(
                path
                for path in self._directory.iterdir()
                if path.suffix.lower() in _IMAGE_EXTENSIONS and path.name not in self._seen
            )
            for path in candidates:
                self._seen.add(path.name)
                image = cv2.imread(str(path))
                if image is None:
                    continue  # unreadable/corrupt file: skip it, keep looking
                frame = Frame(
                    camera_id=self._camera_id, image=image, frame_index=self._frame_index
                )
                self._frame_index += 1
                return frame

            if not self._watch:
                return None  # batch mode: nothing left, we're done
            self._stop_event.wait(self._poll_seconds)

    def close(self) -> None:
        self._open = False
        self._stop_event.set()

    @property
    def is_open(self) -> bool:
        return self._open
