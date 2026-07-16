"""Repository CRUD tests against a real (temp file) SQLite database.

Uses a real `aiosqlite` engine/session per test, not a mocked session —
this is what actually catches ORM-mapping mistakes (column types, JSON
round-tripping, the SQLite naive-datetime gotcha `UTCDateTime` works around)
that a mocked session would hide.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.config.settings import DatabaseSettings
from sentinel_detect.core.entities.alert import Alert, AlertChannelType, AlertStatus
from sentinel_detect.core.entities.camera import Camera, SourceType
from sentinel_detect.core.entities.configuration import ConfigurationEntry
from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.database.engine import create_engine, create_session_factory, init_models
from sentinel_detect.database.repositories import (
    AlertRepository,
    CameraRepository,
    ConfigurationRepository,
    DetectionRepository,
    EventRepository,
    UserRepository,
)


@pytest.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    db_path = tmp_path / "test.db"
    settings = DatabaseSettings(url=f"sqlite+aiosqlite:///{db_path}")
    engine = create_engine(settings)
    await init_models(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as db_session:
        yield db_session
    await engine.dispose()


def _detection(camera_id: str = "cam-1") -> Detection:
    return Detection(
        camera_id=camera_id,
        detector="person",
        label=DetectionClass.PERSON,
        confidence=0.9,
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        frame_width=640,
        frame_height=480,
    )


def _event(camera_id: str = "cam-1") -> Event:
    return Event(
        camera_id=camera_id,
        type=EventType.PERSON_DETECTED,
        severity=EventSeverity.INFO,
        rule="person_detected",
        track_ids=(1, 2),
        message="a person was detected",
        metadata={"note": "test"},
    )


class TestDetectionRepository:
    async def test_create_and_get_roundtrip(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        detection = _detection()

        await repo.create(detection)
        fetched = await repo.get(detection.id)

        assert fetched == detection

    async def test_get_missing_returns_none(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        assert await repo.get(_detection().id) is None

    async def test_list_orders_most_recent_first(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        older = _detection().model_copy(update={"timestamp": datetime(2020, 1, 1, tzinfo=UTC)})
        newer = _detection().model_copy(update={"timestamp": datetime(2025, 1, 1, tzinfo=UTC)})
        await repo.create(older)
        await repo.create(newer)

        results = await repo.list()

        assert [d.id for d in results] == [newer.id, older.id]

    async def test_list_respects_limit_and_offset(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        for _ in range(5):
            await repo.create(_detection())

        assert len(await repo.list(limit=2)) == 2
        assert len(await repo.list(offset=4, limit=10)) == 1

    async def test_update_persists_changes(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        detection = _detection()
        await repo.create(detection)

        updated = detection.model_copy(update={"confidence": 0.42})
        await repo.update(updated)
        fetched = await repo.get(detection.id)

        assert fetched is not None
        assert fetched.confidence == pytest.approx(0.42)

    async def test_update_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        with pytest.raises(NotFoundError):
            await repo.update(_detection())

    async def test_delete_removes_the_row(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        detection = _detection()
        await repo.create(detection)

        await repo.delete(detection.id)

        assert await repo.get(detection.id) is None

    async def test_delete_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = DetectionRepository(session)
        with pytest.raises(NotFoundError):
            await repo.delete(_detection().id)


class TestEventRepository:
    async def test_create_and_get_roundtrip_preserves_track_ids_and_metadata(
        self, session: AsyncSession
    ) -> None:
        repo = EventRepository(session)
        event = _event()

        await repo.create(event)
        fetched = await repo.get(event.id)

        assert fetched == event
        assert fetched is not None
        assert fetched.track_ids == (1, 2)
        assert fetched.metadata == {"note": "test"}

    async def test_list_orders_most_recent_first(self, session: AsyncSession) -> None:
        repo = EventRepository(session)
        older = _event().model_copy(update={"timestamp": datetime(2020, 1, 1, tzinfo=UTC)})
        newer = _event().model_copy(update={"timestamp": datetime(2025, 1, 1, tzinfo=UTC)})
        await repo.create(older)
        await repo.create(newer)

        results = await repo.list()

        assert [e.id for e in results] == [newer.id, older.id]

    async def test_update_persists_changes(self, session: AsyncSession) -> None:
        repo = EventRepository(session)
        event = _event()
        await repo.create(event)

        await repo.update(event.model_copy(update={"message": "updated message"}))
        fetched = await repo.get(event.id)

        assert fetched is not None
        assert fetched.message == "updated message"

    async def test_update_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = EventRepository(session)
        with pytest.raises(NotFoundError):
            await repo.update(_event())

    async def test_delete_removes_the_row(self, session: AsyncSession) -> None:
        repo = EventRepository(session)
        event = _event()
        await repo.create(event)

        await repo.delete(event.id)

        assert await repo.get(event.id) is None

    async def test_delete_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = EventRepository(session)
        with pytest.raises(NotFoundError):
            await repo.delete(_event().id)


class TestAlertRepository:
    async def test_create_requires_the_referenced_event_to_already_exist(
        self, session: AsyncSession
    ) -> None:
        event_repo = EventRepository(session)
        alert_repo = AlertRepository(session)
        event = _event()

        await event_repo.create(event)  # must precede the alert (real FK)
        alert = Alert(event=event, channel=AlertChannelType.WEBHOOK, status=AlertStatus.SENT)
        await alert_repo.create(alert)
        await session.flush()

        fetched = await alert_repo.get(alert.id)
        assert fetched is not None
        assert fetched.event == event
        assert fetched.channel is AlertChannelType.WEBHOOK

    async def test_update_changes_status_and_delivered_at(self, session: AsyncSession) -> None:
        event_repo = EventRepository(session)
        alert_repo = AlertRepository(session)
        event = _event()
        await event_repo.create(event)
        alert = Alert(
            event=event, channel=AlertChannelType.EMAIL, status=AlertStatus.FAILED, error="boom"
        )

        await alert_repo.create(alert)
        delivered = alert.model_copy(
            update={"status": AlertStatus.SENT, "error": None, "delivered_at": datetime.now(UTC)}
        )
        await alert_repo.update(delivered)
        fetched = await alert_repo.get(alert.id)

        assert fetched is not None
        assert fetched.status is AlertStatus.SENT
        assert fetched.error is None
        assert fetched.delivered_at is not None

    async def test_list_orders_most_recent_first(self, session: AsyncSession) -> None:
        event_repo = EventRepository(session)
        alert_repo = AlertRepository(session)
        event = _event()
        await event_repo.create(event)

        older = Alert(
            event=event,
            channel=AlertChannelType.REST,
            status=AlertStatus.SENT,
            created_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        newer = Alert(
            event=event,
            channel=AlertChannelType.WEBSOCKET,
            status=AlertStatus.SENT,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        await alert_repo.create(older)
        await alert_repo.create(newer)

        results = await alert_repo.list()

        assert [a.id for a in results] == [newer.id, older.id]

    async def test_update_missing_raises_not_found(self, session: AsyncSession) -> None:
        alert_repo = AlertRepository(session)
        alert = Alert(event=_event(), channel=AlertChannelType.REST, status=AlertStatus.SENT)

        with pytest.raises(NotFoundError):
            await alert_repo.update(alert)

    async def test_delete_removes_the_row(self, session: AsyncSession) -> None:
        event_repo = EventRepository(session)
        alert_repo = AlertRepository(session)
        event = _event()
        await event_repo.create(event)
        alert = Alert(event=event, channel=AlertChannelType.REST, status=AlertStatus.SENT)
        await alert_repo.create(alert)

        await alert_repo.delete(alert.id)

        assert await alert_repo.get(alert.id) is None

    async def test_delete_missing_raises_not_found(self, session: AsyncSession) -> None:
        alert_repo = AlertRepository(session)
        alert = Alert(event=_event(), channel=AlertChannelType.REST, status=AlertStatus.SENT)

        with pytest.raises(NotFoundError):
            await alert_repo.delete(alert.id)


class TestCameraRepository:
    async def test_create_and_get_roundtrip(self, session: AsyncSession) -> None:
        repo = CameraRepository(session)
        camera = Camera(
            id="cam-1",
            name="Front Door",
            source_type=SourceType.RTSP,
            uri="rtsp://example.com/1",
            enabled_detectors=("person", "vehicle"),
        )

        await repo.create(camera)
        fetched = await repo.get("cam-1")

        assert fetched == camera

    async def test_update_changes_enabled_flag(self, session: AsyncSession) -> None:
        repo = CameraRepository(session)
        camera = Camera(id="cam-1", name="Front Door", source_type=SourceType.RTSP, uri="rtsp://x")
        await repo.create(camera)

        await repo.update(camera.model_copy(update={"enabled": False}))
        fetched = await repo.get("cam-1")

        assert fetched is not None
        assert fetched.enabled is False

    async def test_update_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = CameraRepository(session)
        camera = Camera(id="cam-x", name="X", source_type=SourceType.RTSP, uri="rtsp://x")

        with pytest.raises(NotFoundError):
            await repo.update(camera)

    async def test_delete_removes_the_row(self, session: AsyncSession) -> None:
        repo = CameraRepository(session)
        camera = Camera(id="cam-1", name="Front Door", source_type=SourceType.RTSP, uri="rtsp://x")
        await repo.create(camera)

        await repo.delete("cam-1")

        assert await repo.get("cam-1") is None

    async def test_delete_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = CameraRepository(session)
        with pytest.raises(NotFoundError):
            await repo.delete("does-not-exist")


class TestUserRepository:
    async def test_create_and_get_roundtrip(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = User(
            username="alice", email="alice@example.com", hashed_password="hash", role=UserRole.ADMIN
        )

        await repo.create(user)
        fetched = await repo.get(user.id)

        assert fetched == user

    async def test_get_by_username(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = User(username="bob", email="bob@example.com", hashed_password="hash")
        await repo.create(user)

        fetched = await repo.get_by_username("bob")

        assert fetched == user
        assert await repo.get_by_username("nobody") is None

    async def test_list_orders_most_recent_first(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        older = User(
            username="older",
            email="older@example.com",
            hashed_password="hash",
            created_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        newer = User(
            username="newer",
            email="newer@example.com",
            hashed_password="hash",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        await repo.create(older)
        await repo.create(newer)

        results = await repo.list()

        assert [u.id for u in results] == [newer.id, older.id]

    async def test_update_persists_changes(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = User(username="alice", email="alice@example.com", hashed_password="hash")
        await repo.create(user)

        await repo.update(user.model_copy(update={"is_active": False}))
        fetched = await repo.get(user.id)

        assert fetched is not None
        assert fetched.is_active is False

    async def test_update_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = User(username="x", email="x@example.com", hashed_password="h")

        with pytest.raises(NotFoundError):
            await repo.update(user)

    async def test_delete_removes_the_row(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        user = User(username="alice", email="alice@example.com", hashed_password="hash")
        await repo.create(user)

        await repo.delete(user.id)

        assert await repo.get(user.id) is None

    async def test_delete_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = UserRepository(session)
        with pytest.raises(NotFoundError):
            await repo.delete(User(username="x", email="x@example.com", hashed_password="h").id)


class TestConfigurationRepository:
    async def test_create_and_get_roundtrip_with_structured_value(
        self, session: AsyncSession
    ) -> None:
        repo = ConfigurationRepository(session)
        entry = ConfigurationEntry(
            key="detector_defaults", value={"confidence": 0.5, "enabled": True}
        )

        await repo.create(entry)
        fetched = await repo.get("detector_defaults")

        assert fetched == entry
        assert fetched is not None
        assert fetched.value == {"confidence": 0.5, "enabled": True}

    async def test_update_changes_value(self, session: AsyncSession) -> None:
        repo = ConfigurationRepository(session)
        entry = ConfigurationEntry(key="max_fps", value=30)
        await repo.create(entry)

        await repo.update(entry.model_copy(update={"value": 60}))
        fetched = await repo.get("max_fps")

        assert fetched is not None
        assert fetched.value == 60

    async def test_update_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = ConfigurationRepository(session)
        with pytest.raises(NotFoundError):
            await repo.update(ConfigurationEntry(key="does-not-exist", value=1))

    async def test_delete_removes_the_row(self, session: AsyncSession) -> None:
        repo = ConfigurationRepository(session)
        entry = ConfigurationEntry(key="max_fps", value=30)
        await repo.create(entry)

        await repo.delete("max_fps")

        assert await repo.get("max_fps") is None

    async def test_delete_missing_raises_not_found(self, session: AsyncSession) -> None:
        repo = ConfigurationRepository(session)
        with pytest.raises(NotFoundError):
            await repo.delete("does-not-exist")
