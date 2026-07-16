"""Input source port: images, video files, webcams, RTSP/IP cameras, directories."""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel_detect.core.entities.media import Frame
from sentinel_detect.core.registry import Registry


class BaseVideoSource(ABC):
    """Port for anything that yields a sequence of `Frame`s for one camera.

    Implementations are iterable so the streaming pipeline can `for frame in
    source:` regardless of whether the underlying source is a finite video
    file, a directory of images, or an unbounded RTSP stream.
    """

    @abstractmethod
    def open(self) -> None:
        """Acquire the underlying resource (device handle, socket, file). Idempotent."""

    @abstractmethod
    def read(self) -> Frame | None:
        """Return the next frame, or None if the source is exhausted/disconnected."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying resource. Idempotent.

        `read()` runs on a worker thread (`asyncio.to_thread`) so a live
        stream's cancellation can call `close()` concurrently with an
        in-flight `read()` to interrupt it promptly. Implementations should
        make `read()` return `None` soon after `close()` is called from
        another thread where that's feasible (e.g. a polling loop waking on
        an event) rather than only taking effect on the next call.
        """

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the source is currently open and expected to yield frames."""

    def __iter__(self) -> BaseVideoSource:
        self.open()
        return self

    def __next__(self) -> Frame:
        frame = self.read()
        if frame is None:
            self.close()
            raise StopIteration
        return frame


video_source_registry: Registry[BaseVideoSource] = Registry("video_source")
