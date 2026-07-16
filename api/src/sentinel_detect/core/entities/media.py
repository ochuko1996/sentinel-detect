"""Frame entity: the unit of work flowing through the detection pipeline.

Unlike the other entities in this package, `Frame` is a plain slotted
dataclass rather than a pydantic model. It wraps a raw `numpy.ndarray` and is
constructed once per frame on the hot path (potentially dozens of times per
second per camera) — pydantic's validation overhead is unwarranted here, and
`numpy.ndarray` cannot be validated by pydantic without an escape hatch anyway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np


@dataclass(slots=True, frozen=True)
class Frame:
    """A single BGR image (as produced by OpenCV) from a camera source."""

    camera_id: str
    image: np.ndarray
    """HxWx3 uint8 array in BGR channel order."""
    frame_index: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])
