"""Integration tests for camera CRUD, including RBAC enforcement."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from sentinel_detect.core.entities.user import UserRole
from sentinel_detect.main import app

from ._auth_helpers import create_user_and_get_token


def _camera_id() -> str:
    return f"cam-{uuid4().hex[:12]}"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_viewer_can_list_and_read_but_not_create_cameras() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)

        list_response = client.get("/cameras", headers=_auth(token))
        create_response = client.post(
            "/camera",
            json={
                "id": _camera_id(),
                "name": "Front Door",
                "source_type": "rtsp",
                "uri": "rtsp://example.com/1",
            },
            headers=_auth(token),
        )

    assert list_response.status_code == 200
    assert create_response.status_code == 403


def test_operator_can_create_read_and_update_a_camera() -> None:
    camera_id = _camera_id()

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)

        create_response = client.post(
            "/camera",
            json={
                "id": camera_id,
                "name": "Front Door",
                "source_type": "rtsp",
                "uri": "rtsp://example.com/1",
                "enabled_detectors": ["person", "vehicle"],
            },
            headers=_auth(token),
        )
        get_response = client.get(f"/cameras/{camera_id}", headers=_auth(token))
        update_response = client.put(
            f"/camera/{camera_id}", json={"enabled": False}, headers=_auth(token)
        )

    assert create_response.status_code == 201
    assert create_response.json()["id"] == camera_id
    assert get_response.status_code == 200
    assert get_response.json()["enabled_detectors"] == ["person", "vehicle"]
    assert update_response.status_code == 200
    assert update_response.json()["enabled"] is False
    # Untouched fields survive a partial update.
    assert update_response.json()["name"] == "Front Door"


def test_creating_a_duplicate_camera_id_conflicts() -> None:
    camera_id = _camera_id()
    payload = {
        "id": camera_id,
        "name": "Front Door",
        "source_type": "rtsp",
        "uri": "rtsp://example.com/1",
    }

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        first = client.post("/camera", json=payload, headers=_auth(token))
        second = client.post("/camera", json=payload, headers=_auth(token))

    assert first.status_code == 201
    assert second.status_code == 409


def test_getting_a_nonexistent_camera_is_404() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)
        response = client.get("/cameras/does-not-exist", headers=_auth(token))

    assert response.status_code == 404


def test_updating_a_nonexistent_camera_is_404() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        response = client.put(
            "/camera/does-not-exist", json={"enabled": False}, headers=_auth(token)
        )

    assert response.status_code == 404


def test_deleting_a_nonexistent_camera_is_404() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.ADMIN)
        response = client.delete("/camera/does-not-exist", headers=_auth(token))

    assert response.status_code == 404


def test_operator_cannot_delete_a_camera_but_admin_can() -> None:
    camera_id = _camera_id()
    payload = {
        "id": camera_id,
        "name": "Front Door",
        "source_type": "rtsp",
        "uri": "rtsp://example.com/1",
    }

    with TestClient(app) as client:
        operator_token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        admin_token = create_user_and_get_token(client, role=UserRole.ADMIN)

        client.post("/camera", json=payload, headers=_auth(operator_token))
        operator_delete = client.delete(f"/camera/{camera_id}", headers=_auth(operator_token))
        admin_delete = client.delete(f"/camera/{camera_id}", headers=_auth(admin_token))

    assert operator_delete.status_code == 403
    assert admin_delete.status_code == 204


def test_creating_a_camera_with_a_restricted_zone_region_roundtrips() -> None:
    camera_id = _camera_id()
    payload = {
        "id": camera_id,
        "name": "Loading Dock",
        "source_type": "rtsp",
        "uri": "rtsp://example.com/2",
        "regions": [
            {
                "id": "zone-1",
                "camera_id": camera_id,
                "name": "No-Go Zone",
                "type": "restricted_zone",
                "polygon": {
                    "points": [
                        {"x": 0, "y": 0},
                        {"x": 100, "y": 0},
                        {"x": 100, "y": 100},
                    ]
                },
            }
        ],
    }

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        create_response = client.post("/camera", json=payload, headers=_auth(token))
        get_response = client.get(f"/cameras/{camera_id}", headers=_auth(token))

    assert create_response.status_code == 201
    assert len(get_response.json()["regions"]) == 1
    assert get_response.json()["regions"][0]["type"] == "restricted_zone"
