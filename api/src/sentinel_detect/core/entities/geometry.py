"""Geometric primitives shared by detections, tracking, and ROIs."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class Point(BaseModel, frozen=True):
    """A pixel coordinate in a frame."""

    x: float
    y: float


class BoundingBox(BaseModel, frozen=True):
    """Axis-aligned box in absolute pixel coordinates, top-left origin."""

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def _check_ordering(self) -> BoundingBox:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError(
                f"invalid box: (x1={self.x1}, y1={self.y1}) must be "
                f"strictly less than (x2={self.x2}, y2={self.y2})"
            )
        return self

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point(x=(self.x1 + self.x2) / 2, y=(self.y1 + self.y2) / 2)

    def iou(self, other: BoundingBox) -> float:
        """Intersection-over-union with `other`, used by tracking/NMS."""
        ix1, iy1 = max(self.x1, other.x1), max(self.y1, other.y1)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        intersection = (ix2 - ix1) * (iy2 - iy1)
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0


class Polygon(BaseModel, frozen=True):
    """An ordered sequence of points defining a closed region (an ROI)."""

    points: tuple[Point, ...]

    @model_validator(mode="after")
    def _check_min_points(self) -> Polygon:
        if len(self.points) < 3:
            raise ValueError("a polygon requires at least 3 points")
        return self

    def contains_point(self, point: Point) -> bool:
        """Ray-casting point-in-polygon test."""
        inside = False
        n = len(self.points)
        j = n - 1
        for i in range(n):
            xi, yi = self.points[i].x, self.points[i].y
            xj, yj = self.points[j].x, self.points[j].y
            intersects = ((yi > point.y) != (yj > point.y)) and (
                point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside
