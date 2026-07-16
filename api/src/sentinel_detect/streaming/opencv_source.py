"""BaseVideoSource backed by `cv2.VideoCapture`.

`cv2.VideoCapture` accepts either an integer device index (webcam/USB) or a
URL/path string (RTSP, an IP camera's stream URL, or a local video file)
uniformly, so one implementation covers `SourceType.WEBCAM`, `.USB`,
`.RTSP`, `.IP_CAMERA`, and `.VIDEO_FILE` — see `streaming/factory.py`.
"""

from __future__ import annotations

import cv2

from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.exceptions import VideoSourceError
from sentinel_detect.core.interfaces.video_source import BaseVideoSource, video_source_registry


class OpenCVVideoSource(BaseVideoSource):
    def __init__(self, camera_id: str, uri: str) -> None:
        self._camera_id = camera_id
        self._uri = uri
        self._capture: cv2.VideoCapture | None = None
        self._frame_index = 0

    def open(self) -> None:
        if self._capture is not None:
            return
        # A purely-numeric uri means "device index" (webcam/USB); anything
        # else (rtsp://..., http://..., a filesystem path) is passed through
        # to VideoCapture as-is.
        source: int | str = int(self._uri) if self._uri.isdigit() else self._uri
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise VideoSourceError(f"could not open video source '{self._uri}'")
        self._capture = capture

    def read(self) -> Frame | None:
        if self._capture is None:
            raise VideoSourceError("source not open; call open() first")
        ok, image = self._capture.read()
        if not ok:
            return None
        frame = Frame(camera_id=self._camera_id, image=image, frame_index=self._frame_index)
        self._frame_index += 1
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()


# Registered under every SourceType it actually handles (see
# streaming/factory.py), rather than a single generic key, since the
# registry is keyed by SourceType.value elsewhere.
for _key in ("webcam", "usb", "rtsp", "ip_camera", "video_file"):
    video_source_registry.register(_key)(OpenCVVideoSource)
