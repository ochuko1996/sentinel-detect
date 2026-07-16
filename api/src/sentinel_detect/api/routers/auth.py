"""POST /auth/login — issues a JWT access token for a username/password pair."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from sentinel_detect.api.dependencies.config import SettingsDep
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.api.schemas.auth import TokenResponse
from sentinel_detect.database.repositories import UserRepository
from sentinel_detect.security.passwords import verify_password
from sentinel_detect.security.tokens import create_access_token
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    settings: SettingsDep,
    session: DbSessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """Standard OAuth2 password flow: exchange a username/password for a JWT.

    Use the returned `access_token` as `Authorization: Bearer <token>` on
    subsequent requests. There's no `POST /users` endpoint — see
    `SENTINEL_SECURITY__BOOTSTRAP_ADMIN_*` in the README for creating the
    first account. An `X-API-Key` header is a static-key alternative to
    this flow for service/machine callers.
    """
    user = await UserRepository(session).get_by_username(form_data.username)

    if (
        user is None
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        logger.warning("login_failed", username=form_data.username)  # audit log
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user.id, username=user.username, role=user.role, settings=settings.security
    )
    logger.info("login_succeeded", username=user.username, role=user.role.value)  # audit log
    return TokenResponse(access_token=token, username=user.username, role=user.role.value)
