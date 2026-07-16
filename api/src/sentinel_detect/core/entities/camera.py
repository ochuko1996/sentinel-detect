"""Camera and Region-of-Interest entities."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from sentinel_detect.core.entities.geometry import Point, Polygon


class SourceType(StrEnum):
    """Kind of input feed a camera represents."""

    IMAGE = "image"
    VIDEO_FILE = "video_file"
    WEBCAM = "webcam"
    USB = "usb"
    RTSP = "rtsp"
    IP_CAMERA = "ip_camera"
    DIRECTORY = "directory"


class RegionType(StrEnum):
    """Semantics of a region of interest; event rules key off this."""

    RESTRICTED_ZONE = "restricted_zone"
    SAFE_ZONE = "safe_zone"
    ENTRY_ZONE = "entry_zone"
    EXIT_ZONE = "exit_zone"
    TRIPWIRE = "tripwire"


class Region(BaseModel, frozen=True):
    """A named zone or tripwire on a specific camera's frame.

    A `TRIPWIRE` uses exactly two points (a line); all other region types use
    a `Polygon` with 3+ points.
    """

    id: str
    camera_id: str
    name: str
    type: RegionType
    polygon: Polygon | None = None
    line: tuple[Point, Point] | None = None

    def model_post_init(self, __context: object) -> None:
        if self.type is RegionType.TRIPWIRE and self.line is None:
            raise ValueError("a TRIPWIRE region requires `line`")
        if self.type is not RegionType.TRIPWIRE and self.polygon is None:
            raise ValueError(f"a {self.type} region requires `polygon`")


class Camera(BaseModel, frozen=True):
    """A configured input source, along with the detectors and regions applied to it."""

    id: str
    name: str
    source_type: SourceType
    uri: str
    """Filesystem path, device index, RTSP URL, or directory to watch."""
    enabled: bool = True
    enabled_detectors: tuple[str, ...] = Field(default_factory=tuple)
    regions: tuple[Region, ...] = Field(default_factory=tuple)
    frame_rate_limit: float | None = Field(
        default=None, gt=0, description="Max frames/sec to process; None = unlimited."
    )
    inference_size: tuple[int, int] = (640, 640)
