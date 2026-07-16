"""Runtime-configurable key/value settings, distinct from `AppSettings`.

`AppSettings` (env vars + `.env`) is the source of truth for how the process
itself boots (which detectors/rules/channels to build, model paths, ...) and
requires a restart to change. `ConfigurationEntry` is for values an operator
should be able to change at runtime via the future `POST /config` endpoint
(Phase 7) without restarting the process — this entity only defines the
persisted shape; nothing reads these back into `AppSettings` yet.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

ConfigurationValue = str | int | float | bool | dict[str, Any] | list[Any] | None


class ConfigurationEntry(BaseModel, frozen=True):
    key: str
    value: ConfigurationValue
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
