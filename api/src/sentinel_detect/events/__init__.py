"""BaseEventRule implementations: the rule engine.

Importing this package registers every built-in rule as a side effect —
required before `build_enabled_rules` can resolve one by key.
"""

from sentinel_detect.events import (  # noqa: F401
    crowd,
    detected,
    loitering,
    object_state,
    regions,
)
from sentinel_detect.events.factory import build_enabled_rules

__all__ = ["build_enabled_rules"]

