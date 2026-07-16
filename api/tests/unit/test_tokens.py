from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from sentinel_detect.config.settings import SecuritySettings
from sentinel_detect.core.entities.user import UserRole
from sentinel_detect.core.exceptions import AuthenticationError
from sentinel_detect.security.tokens import create_access_token, decode_access_token


def _settings(**overrides: object) -> SecuritySettings:
    return SecuritySettings(**overrides)  # type: ignore[arg-type]


def test_create_and_decode_roundtrip() -> None:
    settings = _settings()
    user_id = uuid4()

    token = create_access_token(
        user_id=user_id, username="alice", role=UserRole.ADMIN, settings=settings
    )
    payload = decode_access_token(token, settings)

    assert payload.user_id == user_id
    assert payload.username == "alice"
    assert payload.role is UserRole.ADMIN


def test_decode_rejects_a_token_signed_with_a_different_secret() -> None:
    settings_a = _settings(jwt_secret="secret-a")
    settings_b = _settings(jwt_secret="secret-b")
    token = create_access_token(
        user_id=uuid4(), username="alice", role=UserRole.VIEWER, settings=settings_a
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings_b)


def test_decode_rejects_an_expired_token() -> None:
    settings = _settings(jwt_secret="s", jwt_algorithm="HS256")
    expired_payload = {
        "sub": str(uuid4()),
        "username": "alice",
        "role": "viewer",
        "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(expired_payload, "s", algorithm="HS256")

    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings)


def test_decode_rejects_garbage_input() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("not-a-jwt-at-all", _settings())


def test_decode_rejects_a_token_missing_required_claims() -> None:
    settings = _settings(jwt_secret="s")
    token = jwt.encode({"sub": "not-a-uuid"}, "s", algorithm="HS256")

    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings)
