"""ASGI application entrypoint.

Run with:  uvicorn sentinel_detect.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sentinel_detect.alerts import (
    AlertResources,
    AlertStore,
    ConnectionManager,
    build_enabled_channels,
)
from sentinel_detect.api.routers import (
    alerts,
    auth,
    cameras,
    detect,
    detections,
    events,
    health,
    metrics,
    stream,
    websocket,
)
from sentinel_detect.api.routers import config as config_router
from sentinel_detect.config.settings import get_settings
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.database import create_engine, create_session_factory, init_models
from sentinel_detect.database.repositories import UserRepository
from sentinel_detect.detectors import build_enabled_detectors
from sentinel_detect.events import build_enabled_rules
from sentinel_detect.models import ModelManager
from sentinel_detect.security import RateLimitMiddleware, hash_password
from sentinel_detect.services import (
    AlertEngine,
    DetectionService,
    EventEngine,
    PipelineService,
    TrackingService,
)
from sentinel_detect.streaming import StreamBroadcaster, StreamManager
from sentinel_detect.tracking import build_tracker
from sentinel_detect.utils.logging import configure_logging, get_logger
from sentinel_detect.utils.metrics import MetricsMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.logging)

    db_engine = create_engine(settings.database)
    db_session_factory = create_session_factory(db_engine)
    await init_models(db_engine)

    model_manager = ModelManager(settings.models)
    detectors = build_enabled_detectors(settings, model_manager)

    for model_key, model in model_manager.loaded_models().items():
        try:
            model.warmup()
        except Exception:
            logger.warning("model_warmup_failed", model_key=model_key, exc_info=True)

    detection_service = DetectionService(detectors)
    tracker = build_tracker(settings)
    tracking_service = TrackingService(detection_service, tracker)

    rules = build_enabled_rules(settings)
    event_engine = EventEngine(rules)
    pipeline_service = PipelineService(tracking_service, event_engine)

    rest_settings = settings.alerts.get("rest")
    max_stored = int(rest_settings.params.get("max_stored", "500")) if rest_settings else 500

    connection_manager = ConnectionManager()
    alert_store = AlertStore(max_size=max_stored)
    alert_resources = AlertResources(connection_manager=connection_manager, alert_store=alert_store)
    alert_channels = build_enabled_channels(settings, alert_resources)
    alert_engine = AlertEngine(alert_channels)

    stream_broadcaster = StreamBroadcaster()
    stream_manager = StreamManager(
        pipeline_service, alert_engine, db_session_factory, stream_broadcaster, settings.pipeline
    )

    app.state.db_engine = db_engine
    app.state.db_session_factory = db_session_factory
    app.state.model_manager = model_manager
    app.state.detection_service = detection_service
    app.state.pipeline_service = pipeline_service
    app.state.connection_manager = connection_manager
    app.state.alert_store = alert_store
    app.state.alert_engine = alert_engine
    app.state.stream_broadcaster = stream_broadcaster
    app.state.stream_manager = stream_manager

    # Bootstrap an ADMIN user if configured and none exists yet — solves the
    # chicken-and-egg problem of needing a user to log in as before any
    # user-management endpoint exists. No-op unless an operator explicitly
    # sets a bootstrap password.
    if settings.security.bootstrap_admin_password:
        async with db_session_factory() as session:
            user_repo = UserRepository(session)
            username = settings.security.bootstrap_admin_username
            if await user_repo.get_by_username(username) is None:
                await user_repo.create(
                    User(
                        username=username,
                        email=f"{username}@local",
                        hashed_password=hash_password(settings.security.bootstrap_admin_password),
                        role=UserRole.ADMIN,
                    )
                )
                await session.commit()
                logger.info("bootstrap_admin_created", username=username)  # audit log

    logger.info(
        "startup",
        environment=settings.environment,
        database_url=settings.database.url,
        configured_detectors=settings.enabled_detector_keys(),
        active_detectors=detection_service.active_detector_keys(),
        configured_event_rules=settings.enabled_event_rule_keys(),
        active_event_rules=event_engine.active_rule_keys(),
        configured_alert_channels=settings.enabled_alert_channel_keys(),
        active_alert_channels=alert_engine.active_channel_keys(),
    )
    yield
    await stream_manager.stop_all()
    await db_engine.dispose()
    logger.info("shutdown")


_OPENAPI_DESCRIPTION = """\
AI-powered object detection and security analytics platform: images,
video uploads, and live streams (webcam/USB/RTSP/IP camera/directory feed)
all flow through the same detection → tracking → event → alert → storage
pipeline.

**Auth:** most endpoints accept either a JWT bearer token (`POST
/auth/login`) or a static `X-API-Key` header. `/detect/image`,
`/detect/video`, `/alerts`, `/ws/alerts`, `/health`, and `/metrics` are
intentionally open (see docs/architecture.md for why); everything else —
camera/config management and the streaming control endpoints — requires
authentication, gated further by role (VIEWER < OPERATOR < ADMIN).

**Full design rationale** (why each piece is built the way it is, what's
deliberately out of scope, and what every phase verified) lives in
`docs/architecture.md` in the repository — this page documents the wire
contract, not the reasoning behind it.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=_OPENAPI_DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings.security)

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(detect.router)
    app.include_router(alerts.router)
    app.include_router(websocket.router)
    app.include_router(cameras.router)
    app.include_router(events.router)
    app.include_router(detections.router)
    app.include_router(config_router.router)
    app.include_router(stream.router)
    return app


app = create_app()
