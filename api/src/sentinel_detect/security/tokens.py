"""JWT access token creation and verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pydantic import BaseModel

from sentinel_detect.config.settings import SecuritySettings
from sentinel_detect.core.entities.user import UserRole
from sentinel_detect.core.exceptions import AuthenticationError


class TokenPayload(BaseModel):
    user_id: UUID
    username: str
    role: UserRole
    expires_at: datetime


def create_access_token(
    *, user_id: UUID, username: str, role: UserRole, settings: SecuritySettings
) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: SecuritySettings) -> TokenPayload:
    """Raise `AuthenticationError` on an invalid, expired, or malformed token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError(f"invalid or expired token: {exc}") from exc

    try:
        return TokenPayload(
            user_id=UUID(payload["sub"]),
            username=payload["username"],
            role=UserRole(payload["role"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (KeyError, ValueError) as exc:
        raise AuthenticationError(f"malformed token payload: {exc}") from exc
