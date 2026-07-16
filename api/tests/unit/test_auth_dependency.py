"""Hermetic tests for `api.dependencies.auth`.

Calls `get_current_user`/`require_role` directly rather than through
FastAPI's DI (the `Annotated[..., Depends(...)]` aliases are ordinary types
at the Python level, so the functions are independently callable) —
constructing fresh `AppSettings`/a temp-file DB session per test rather than
relying on the shared app's already-resolved (memoized) settings, so this
can freely test API-key configurations the shared app wasn't booted with.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from sentinel_detect.api.dependencies.auth import get_current_user, require_role
from sentinel_detect.config.settings import AppSettings, DatabaseSettings
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.database.engine import create_engine, create_session_factory, init_models
from sentinel_detect.database.repositories import UserRepository
from sentinel_detect.security.tokens import create_access_token


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    db_settings = DatabaseSettings(url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    engine = create_engine(db_settings)
    await init_models(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as db_session:
        yield db_session
    await engine.dispose()


async def test_api_key_grants_admin_equivalent_access_when_configured(
    session: AsyncSession,
) -> None:
    settings = AppSettings(_env_file=None)
    settings.security.api_keys = ["my-service-key"]

    user = await get_current_user(
        _request({"X-API-Key": "my-service-key"}), settings, session, token=None
    )

    assert user.role is UserRole.ADMIN
    assert user.username == "api-key"


async def test_api_key_is_rejected_when_not_configured(session: AsyncSession) -> None:
    settings = AppSettings(_env_file=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            _request({"X-API-Key": "not-configured"}), settings, session, token=None
        )

    assert exc_info.value.status_code == 401


async def test_missing_credentials_raises_401(session: AsyncSession) -> None:
    settings = AppSettings(_env_file=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_request({}), settings, session, token=None)

    assert exc_info.value.status_code == 401


async def test_valid_jwt_resolves_to_the_real_user(session: AsyncSession) -> None:
    settings = AppSettings(_env_file=None)
    real_user = User(
        username="alice", email="alice@example.com", hashed_password="h", role=UserRole.OPERATOR
    )
    await UserRepository(session).create(real_user)
    await session.commit()

    token = create_access_token(
        user_id=real_user.id,
        username=real_user.username,
        role=real_user.role,
        settings=settings.security,
    )

    resolved = await get_current_user(_request({}), settings, session, token=token)

    assert resolved == real_user


async def test_jwt_for_a_nonexistent_user_is_rejected(session: AsyncSession) -> None:
    settings = AppSettings(_env_file=None)
    token = create_access_token(
        user_id=uuid4(), username="ghost", role=UserRole.ADMIN, settings=settings.security
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_request({}), settings, session, token=token)

    assert exc_info.value.status_code == 401


async def test_jwt_for_an_inactive_user_is_rejected(session: AsyncSession) -> None:
    settings = AppSettings(_env_file=None)
    inactive_user = User(
        username="bob", email="bob@example.com", hashed_password="h", is_active=False
    )
    await UserRepository(session).create(inactive_user)
    await session.commit()

    token = create_access_token(
        user_id=inactive_user.id,
        username=inactive_user.username,
        role=inactive_user.role,
        settings=settings.security,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_request({}), settings, session, token=token)

    assert exc_info.value.status_code == 401


def test_require_role_allows_a_sufficient_role() -> None:
    check = require_role(UserRole.OPERATOR)
    user = User(username="op", email="op@example.com", hashed_password="h", role=UserRole.ADMIN)

    assert check(user) == user


def test_require_role_rejects_an_insufficient_role() -> None:
    check = require_role(UserRole.ADMIN)
    user = User(username="viewer", email="v@example.com", hashed_password="h", role=UserRole.VIEWER)

    with pytest.raises(HTTPException) as exc_info:
        check(user)

    assert exc_info.value.status_code == 403


def test_require_role_allows_the_exact_required_role() -> None:
    check = require_role(UserRole.VIEWER)
    user = User(username="viewer", email="v@example.com", hashed_password="h", role=UserRole.VIEWER)

    assert check(user) == user
