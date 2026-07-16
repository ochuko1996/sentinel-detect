"""Concrete BaseDetector implementations: person, vehicle, weapon, fire, smoke, ppe, animal.

Importing this package registers every built-in detector into
`detector_registry` as a side effect — required before `build_enabled_detectors`
can resolve any of them by key.
"""

from sentinel_detect.detectors import (  # noqa: F401
    animal,
    fire,
    person,
    ppe,
    smoke,
    vehicle,
    weapon,
)
from sentinel_detect.detectors.factory import build_enabled_detectors

__all__ = ["build_enabled_detectors"]

