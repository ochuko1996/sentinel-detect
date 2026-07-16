"""Integration tests for GET/POST/DELETE /detect/stream and WS /ws/stream/{camera_id}.

Uses a real `DirectoryVideoSource` (a temp directory) rather than a real
camera/RTSP feed — no hardware needed, and the same pipeline components
`/detect/video` already exercises. Deliberately doesn't assert on detection
*contents* (depends on whether the 'vision' extra + real weights are
installed — see test_detect_image_live.py for that), only on the genuine
start/stop/list lifecycle, RBAC, and the websocket actually carrying frames
through from a real background streaming task.
"""

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient

from sentinel_detect.core.entities.user import UserRole
from sentinel_detect.main import app

from ._auth_helpers import create_user_and_get_token


def _camera_id() -> str:
    return f"stream-cam-{uuid4().hex[:12]}"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _write_image(path: Path, fill: int = 10) -> None:
    image = np.full((32, 32, 3), fill, dtype=np.uint8)
    cv2.imwrite(str(path), image)


def _create_camera(
    client: TestClient, token: str, camera_id: str, uri: str, *, enabled: bool = True
) -> None:
    response = client.post(
        "/camera",
        json={
            "id": camera_id,
            "name": "Test Directory Camera",
            "source_type": "directory",
            "uri": uri,
            "enabled": enabled,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text


def _wait_until(predicate: object, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(interval)
    return predicate()  # type: ignore[operator]


def test_starting_listing_and_stopping_a_directory_stream(tmp_path: Path) -> None:
    camera_id = _camera_id()
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    _write_image(images_dir / "a.jpg")
    _write_image(images_dir / "b.jpg")

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        _create_camera(client, token, camera_id, str(images_dir))

        start_response = client.post(
            "/detect/stream", json={"camera_id": camera_id}, headers=_auth(token)
        )
        assert start_response.status_code == 202
        assert start_response.json() == {"camera_id": camera_id, "status": "started"}

        def _has_processed_frames() -> bool:
            listing = client.get("/detect/stream", headers=_auth(token)).json()
            entry = next((s for s in listing if s["camera_id"] == camera_id), None)
            return entry is not None and entry["frames_processed"] >= 2

        assert _wait_until(_has_processed_frames), "stream never processed the seeded frames"

        list_response = client.get("/detect/stream", headers=_auth(token))
        assert list_response.status_code == 200
        entry = next(s for s in list_response.json() if s["camera_id"] == camera_id)
        assert entry["last_error"] is None

        stop_response = client.delete(f"/detect/stream/{camera_id}", headers=_auth(token))
        assert stop_response.status_code == 204

        final_listing = client.get("/detect/stream", headers=_auth(token)).json()
        assert all(s["camera_id"] != camera_id for s in final_listing)


def test_viewer_cannot_start_or_stop_a_stream_but_can_list(tmp_path: Path) -> None:
    camera_id = _camera_id()
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with TestClient(app) as client:
        operator_token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        viewer_token = create_user_and_get_token(client, role=UserRole.VIEWER)
        _create_camera(client, operator_token, camera_id, str(empty_dir))

        list_response = client.get("/detect/stream", headers=_auth(viewer_token))
        start_response = client.post(
            "/detect/stream", json={"camera_id": camera_id}, headers=_auth(viewer_token)
        )

    assert list_response.status_code == 200
    assert start_response.status_code == 403


def test_starting_a_nonexistent_camera_is_404() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        response = client.post(
            "/detect/stream", json={"camera_id": "does-not-exist"}, headers=_auth(token)
        )

    assert response.status_code == 404


def test_starting_a_disabled_camera_is_400(tmp_path: Path) -> None:
    camera_id = _camera_id()
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        _create_camera(client, token, camera_id, str(empty_dir), enabled=False)

        response = client.post(
            "/detect/stream", json={"camera_id": camera_id}, headers=_auth(token)
        )

    assert response.status_code == 400


def test_starting_an_already_active_stream_is_409(tmp_path: Path) -> None:
    camera_id = _camera_id()
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        _create_camera(client, token, camera_id, str(empty_dir))

        first = client.post(
            "/detect/stream", json={"camera_id": camera_id}, headers=_auth(token)
        )
        second = client.post(
            "/detect/stream", json={"camera_id": camera_id}, headers=_auth(token)
        )
        client.delete(f"/detect/stream/{camera_id}", headers=_auth(token))

    assert first.status_code == 202
    assert second.status_code == 409


def test_stopping_an_inactive_stream_is_404() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        response = client.delete("/detect/stream/never-started", headers=_auth(token))

    assert response.status_code == 404


def test_websocket_receives_broadcast_frames_from_a_live_stream(tmp_path: Path) -> None:
    camera_id = _camera_id()
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    _write_image(images_dir / "a.jpg")

    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.OPERATOR)
        _create_camera(client, token, camera_id, str(images_dir))

        with client.websocket_connect(f"/ws/stream/{camera_id}") as websocket:
            start_response = client.post(
                "/detect/stream", json={"camera_id": camera_id}, headers=_auth(token)
            )
            assert start_response.status_code == 202

            message = websocket.receive_json()

        client.delete(f"/detect/stream/{camera_id}", headers=_auth(token))

    assert message["frame_index"] == 0
    assert "timestamp" in message
    assert isinstance(message["tracks"], list)
