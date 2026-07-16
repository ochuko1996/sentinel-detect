"""GET /config, GET /config/{key}, POST /config — runtime key/value configuration entries.

Distinct from `AppSettings` (see `core.entities.configuration`) — mutating
requires ADMIN, the highest bar, since config changes can affect the whole
deployment.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sentinel_detect.api.dependencies.auth import CurrentUserDep, require_role
from sentinel_detect.api.dependencies.database import DbSessionDep
from sentinel_detect.core.entities.configuration import ConfigurationEntry
from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.database.repositories import ConfigurationRepository
from sentinel_detect.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["config"])


@router.get("/config", response_model=list[ConfigurationEntry])
async def list_config(
    session: DbSessionDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConfigurationEntry]:
    """List runtime key/value configuration entries. Requires any
    authenticated principal. Distinct from `AppSettings`/env vars."""
    return await ConfigurationRepository(session).list(offset=offset, limit=limit)


@router.get("/config/{key}", response_model=ConfigurationEntry)
async def get_config(
    key: str, session: DbSessionDep, _user: CurrentUserDep
) -> ConfigurationEntry:
    """Fetch one runtime configuration entry by key. Requires any
    authenticated principal."""
    entry = await ConfigurationRepository(session).get(key)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"config key '{key}' not found"
        )
    return entry


@router.post("/config", response_model=ConfigurationEntry)
async def upsert_config(
    entry: ConfigurationEntry,
    session: DbSessionDep,
    user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> ConfigurationEntry:
    """Create or update a runtime configuration entry (upsert by `key`).
    Requires ADMIN — config changes can affect the whole deployment."""
    repo = ConfigurationRepository(session)
    if await repo.get(entry.key) is None:
        await repo.create(entry)
    else:
        await repo.update(entry)
    await session.commit()
    logger.info("config_updated", key=entry.key, by_user=user.username)  # audit log
    return entry
