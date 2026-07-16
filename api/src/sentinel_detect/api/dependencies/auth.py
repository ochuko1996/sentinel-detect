"""Authentication/authorization dependencies.

`get_current_user` accepts either a valid `X-API-Key` header (checked
against `SecuritySettings.api_keys`) or a valid JWT bearer token — real
auth on both paths, no placeholder. `require_role` layers RBAC on top for
endpoints that need more than VIEWER access.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from sentinel_detect.api.dependencies.config import SettingsDep
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.core.exceptions import AuthenticationError
from sentinel_detect.database.repositories import UserRepository
from sentinel_detect.security.tokens import decode_access_token
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# The identity attached to a request authenticated via a static API key
# rather than a per-user JWT. Not persisted — api_keys are pre-shared
# service credentials, not tied to a specific user account.
_API_KEY_PRINCIPAL = User(
    id=UUID(int=0),
    username="api-key",
    email="api-key@service.local",
    hashed_password="",
    role=UserRole.ADMIN,
)

_ROLE_RANK: dict[UserRole, int] = {UserRole.VIEWER: 0, UserRole.OPERATOR: 1, UserRole.ADMIN: 2}


async def get_current_user(
    request: Request,
    settings: SettingsDep,
    session: DbSessionDep,
    token: Annotated[str | None, Depends(_oauth2_scheme)] = None,
) -> User:
    api_key = request.headers.get(settings.security.api_key_header)
    if api_key and api_key in settings.security.api_keys:
        return _API_KEY_PRINCIPAL

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token, settings.security)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await UserRepository(session).get(payload.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_role(min_role: UserRole) -> Callable[[User], User]:
    """Dependency factory: the current user must have `min_role` or higher
    (VIEWER < OPERATOR < ADMIN)."""

    def _check(user: CurrentUserDep) -> User:
        if _ROLE_RANK[user.role] < _ROLE_RANK[min_role]:
            logger.warning(
                "authorization_denied",
                username=user.username,
                role=user.role.value,
                required_role=min_role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires role '{min_role.value}' or higher",
            )
        return user

    return _check
