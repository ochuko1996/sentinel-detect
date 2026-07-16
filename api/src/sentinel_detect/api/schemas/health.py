"""Response schemas for the health endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    configured_detectors: list[str]
    """Detectors enabled in config, regardless of whether their model actually loaded."""
    active_detectors: list[str]
    """Detectors that are enabled AND whose model loaded successfully at startup."""
    enabled_event_rules: list[str]
    """Event rules enabled in config. Unlike detectors, rules never fail to
    load (no external weights), so there's no separate 'active' subset."""
    configured_alert_channels: list[str]
    """Alert channels enabled in config, regardless of whether they built successfully."""
    active_alert_channels: list[str]
    """Alert channels that are enabled AND correctly configured (e.g. webhook
    with a URL set, email with SMTP credentials set)."""
