"""Shared helper for integration tests needing an authenticated user.

Not a test module itself (no `test_` prefix) — imported by test files that
need a real, working JWT against the app's real, shared database.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.database.repositories import UserRepository
from sentinel_detect.security.passwords import hash_password

TEST_PASSWORD = "test-password-123"


def create_user_and_get_token(client: TestClient, role: UserRole = UserRole.ADMIN) -> str:
    """Seeds a real user directly into the app's database, then logs in
    through the real `POST /auth/login` endpoint to get a genuine JWT."""
    username = f"test-user-{uuid4().hex[:12]}"

    async def _seed() -> None:
        session_factory = client.app.state.db_session_factory  # type: ignore[attr-defined]
        async with session_factory() as session:
            await UserRepository(session).create(
                User(
                    username=username,
                    email=f"{username}@example.com",
                    hashed_password=hash_password(TEST_PASSWORD),
                    role=role,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    response = client.post(
        "/auth/login", data={"username": username, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token
