"""Constant-velocity Kalman filter for bounding-box motion.

Uses the classic SORT/ByteTrack parameterization: state
`[cx, cy, s, r, vcx, vcy, vs]`, where `s` is box area (scale) and `r` is
aspect ratio (width/height). `r` has no velocity term — under smooth motion
an object's aspect ratio is assumed roughly constant, unlike its position
and scale, which do drift frame to frame.

Implemented directly with numpy (no `filterpy` dependency) since the system
is small and fixed-size; the standard SORT reference noise heuristics are
used for `Q`/`R`/initial `P`.
"""

from __future__ import annotations

import numpy as np

from sentinel_detect.core.entities.geometry import BoundingBox

_STATE_DIM = 7
_MEASURE_DIM = 4


class KalmanBoxFilter:
    """Tracks one object's motion as `[cx, cy, s, r, vcx, vcy, vs]`."""

    def __init__(self, bbox: BoundingBox) -> None:
        self._F = np.eye(_STATE_DIM)
        for i in range(3):
            self._F[i, i + 4] = 1.0

        self._H = np.zeros((_MEASURE_DIM, _STATE_DIM))
        for i in range(_MEASURE_DIM):
            self._H[i, i] = 1.0

        self._Q = np.eye(_STATE_DIM)
        self._Q[4:, 4:] *= 0.01
        self._Q[-1, -1] *= 0.01

        self._R = np.eye(_MEASURE_DIM)
        self._R[2:, 2:] *= 10.0

        self._x = np.zeros((_STATE_DIM, 1))
        self._x[:_MEASURE_DIM, 0] = self._to_measurement(bbox)

        self._P = np.eye(_STATE_DIM) * 10.0
        self._P[4:, 4:] *= 1000.0  # unobserved initial velocity: high uncertainty

    @staticmethod
    def _to_measurement(bbox: BoundingBox) -> np.ndarray:
        center = bbox.center
        return np.array([center.x, center.y, bbox.area, bbox.width / bbox.height])

    def predict(self) -> None:
        self._x = self._F @ self._x
        self._P = self._F @ self._P @ self._F.T + self._Q

    def update(self, bbox: BoundingBox) -> None:
        z = self._to_measurement(bbox).reshape(-1, 1)
        y = z - self._H @ self._x
        s = self._H @ self._P @ self._H.T + self._R
        k = self._P @ self._H.T @ np.linalg.inv(s)
        self._x = self._x + k @ y
        self._P = (np.eye(_STATE_DIM) - k @ self._H) @ self._P

    @property
    def bbox(self) -> BoundingBox:
        cx, cy, s, r = self._x[:4, 0]
        s = max(float(s), 1.0)
        r = max(float(r), 1e-3)
        width = float(np.sqrt(s * r))
        height = s / width if width > 0 else 1.0
        return BoundingBox(
            x1=float(cx - width / 2),
            y1=float(cy - height / 2),
            x2=float(cx + width / 2),
            y2=float(cy + height / 2),
        )
