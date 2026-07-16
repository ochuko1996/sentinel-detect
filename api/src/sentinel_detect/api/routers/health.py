"""Liveness/readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from sentinel_detect.api.dependencies.alerts import AlertEngineDep
from sentinel_detect.api.dependencies.config import SettingsDep
from sentinel_detect.api.dependencies.detection import DetectionServiceDep
from sentinel_detect.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: SettingsDep, detection_service: DetectionServiceDep, alert_engine: AlertEngineDep
) -> HealthResponse:
    """Liveness/readiness check. Unauthenticated and rate-limit-exempt.

    Reports both *configured* (what settings say should run) and *active*
    (what actually loaded/is enabled) detectors and alert channels, so a
    detector that failed to load or a channel missing required config is
    observable here rather than silently absent.
    """
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        configured_detectors=settings.enabled_detector_keys(),
        active_detectors=detection_service.active_detector_keys(),
        enabled_event_rules=settings.enabled_event_rule_keys(),
        configured_alert_channels=settings.enabled_alert_channel_keys(),
        active_alert_channels=alert_engine.active_channel_keys(),
    )
