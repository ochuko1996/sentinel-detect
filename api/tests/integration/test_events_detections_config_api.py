"""Integration tests for GET /events, GET /detections, and the /config endpoints."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.entities.user import UserRole
from sentinel_detect.database.repositories import DetectionRepository, EventRepository
from sentinel_detect.main import app

from ._auth_helpers import create_user_and_get_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_event_and_detection(client: TestClient, camera_id: str) -> None:
    async def _seed() -> None:
        session_factory = client.app.state.db_session_factory  # type: ignore[attr-defined]
        async with session_factory() as session:
            await EventRepository(session).create(
                Event(
                    camera_id=camera_id,
                    type=EventType.PERSON_DETECTED,
                    severity=EventSeverity.INFO,
                    rule="person_detected",
                    message="a person was detected",
                )
            )
            await DetectionRepository(session).create(
                Detection(
                    camera_id=camera_id,
                    detector="person",
                    label=DetectionClass.PERSON,
                    confidence=0.9,
                    bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
                    frame_width=640,
                    frame_height=480,
                )
            )
            await session.commit()

    asyncio.run(_seed())


def test_list_events_filters_by_camera_id() -> None:
    camera_id = f"cam-{uuid4().hex[:12]}"

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)
        _seed_event_and_detection(client, camera_id)

        matching = client.get("/events", params={"camera_id": camera_id}, headers=_auth(token))
        other = client.get(
            "/events", params={"camera_id": "some-other-camera"}, headers=_auth(token)
        )

    assert matching.status_code == 200
    assert len(matching.json()) == 1
    assert matching.json()[0]["type"] == "person_detected"
    assert other.json() == []


def test_list_detections_filters_by_camera_id() -> None:
    camera_id = f"cam-{uuid4().hex[:12]}"

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)
        _seed_event_and_detection(client, camera_id)

        matching = client.get(
            "/detections", params={"camera_id": camera_id}, headers=_auth(token)
        )

    assert matching.status_code == 200
    assert len(matching.json()) == 1
    assert matching.json()[0]["label"] == "person"


def test_list_detections_without_a_camera_filter_returns_everything() -> None:
    camera_id = f"cam-{uuid4().hex[:12]}"

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)
        _seed_event_and_detection(client, camera_id)

        response = client.get("/detections", headers=_auth(token))

    assert response.status_code == 200
    assert any(d["label"] == "person" for d in response.json())


def test_events_and_detections_require_authentication() -> None:
    with TestClient(app) as client:
        events_response = client.get("/events")
        detections_response = client.get("/detections")

    assert events_response.status_code == 401
    assert detections_response.status_code == 401


def test_viewer_can_read_config_but_not_write_it() -> None:
    key = f"test-key-{uuid4().hex[:12]}"

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)
        write_response = client.post(
            "/config", json={"key": key, "value": 42}, headers=_auth(token)
        )
        missing_response = client.get(f"/config/{key}", headers=_auth(token))

    assert write_response.status_code == 403
    assert missing_response.status_code == 404


def test_admin_can_create_and_update_a_config_entry() -> None:
    key = f"test-key-{uuid4().hex[:12]}"

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.ADMIN)

        created = client.post("/config", json={"key": key, "value": 30}, headers=_auth(token))
        fetched = client.get(f"/config/{key}", headers=_auth(token))
        updated = client.post("/config", json={"key": key, "value": 60}, headers=_auth(token))
        listed = client.get("/config", headers=_auth(token))

    assert created.status_code == 200
    assert fetched.json()["value"] == 30
    assert updated.json()["value"] == 60
    assert any(entry["key"] == key for entry in listed.json())
