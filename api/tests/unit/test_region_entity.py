"""Tests for Region's model_post_init validation: a TRIPWIRE needs `line`,
every other region type needs `polygon`."""

from __future__ import annotations

import pytest

from sentinel_detect.core.entities.camera import Region, RegionType
from sentinel_detect.core.entities.geometry import Point, Polygon


def test_tripwire_without_a_line_is_rejected() -> None:
    with pytest.raises(ValueError, match="TRIPWIRE"):
        Region(id="r1", camera_id="cam-1", name="Line", type=RegionType.TRIPWIRE)


def test_restricted_zone_without_a_polygon_is_rejected() -> None:
    with pytest.raises(ValueError, match="polygon"):
        Region(id="r1", camera_id="cam-1", name="Zone", type=RegionType.RESTRICTED_ZONE)


def test_tripwire_with_a_line_is_accepted() -> None:
    region = Region(
        id="r1",
        camera_id="cam-1",
        name="Line",
        type=RegionType.TRIPWIRE,
        line=(Point(x=0, y=0), Point(x=10, y=10)),
    )

    assert region.line is not None


def test_restricted_zone_with_a_polygon_is_accepted() -> None:
    region = Region(
        id="r1",
        camera_id="cam-1",
        name="Zone",
        type=RegionType.RESTRICTED_ZONE,
        polygon=Polygon(points=[Point(x=0, y=0), Point(x=10, y=0), Point(x=10, y=10)]),
    )

    assert region.polygon is not None
