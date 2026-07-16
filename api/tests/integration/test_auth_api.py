"""Integration tests for POST /auth/login against the real app + database."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.database.repositories import UserRepository
from sentinel_detect.main import app
from sentinel_detect.security.passwords import hash_password

from ._auth_helpers import TEST_PASSWORD, create_user_and_get_token


def test_login_succeeds_and_the_token_authorizes_a_real_request() -> None:
    with TestClient(app) as client:
        token = create_user_and_get_token(client, role=UserRole.VIEWER)
        response = client.get("/cameras", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_login_fails_with_an_unknown_username() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/auth/login", data={"username": "does-not-exist", "password": "whatever"}
        )

    assert response.status_code == 401


def test_login_fails_with_the_wrong_password() -> None:
    username = f"real-user-{uuid4().hex[:12]}"

    with TestClient(app) as client:

        async def _seed() -> None:
            session_factory = client.app.state.db_session_factory  # type: ignore[attr-defined]
            async with session_factory() as session:
                await UserRepository(session).create(
                    User(
                        username=username,
                        email=f"{username}@example.com",
                        hashed_password=hash_password(TEST_PASSWORD),
                    )
                )
                await session.commit()

        asyncio.run(_seed())

        response = client.post(
            "/auth/login", data={"username": username, "password": "definitely-wrong"}
        )

    assert response.status_code == 401


def test_protected_endpoint_rejects_a_request_with_no_credentials() -> None:
    with TestClient(app) as client:
        response = client.get("/cameras")

    assert response.status_code == 401


def test_protected_endpoint_rejects_an_invalid_bearer_token() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/cameras", headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401


def test_unconfigured_api_key_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.get("/cameras", headers={"X-API-Key": "not-a-configured-key"})

    assert response.status_code == 401
