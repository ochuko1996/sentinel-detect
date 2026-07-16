"""FastAPI dependency provider for application settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from sentinel_detect.config.settings import AppSettings, get_settings

SettingsDep = Annotated[AppSettings, Depends(get_settings)]
