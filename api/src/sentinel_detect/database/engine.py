"""Async SQLAlchemy engine + session factory construction.

`aiosqlite` (SQLite, the zero-setup default) and `asyncpg` (Postgres, the
`postgres` extra) are the two async drivers `DatabaseSettings.url` can name;
everything downstream — models, repositories, sessions — is driver-agnostic.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sentinel_detect.config.settings import DatabaseSettings
from sentinel_detect.database.base import Base

# Importing the models package registers every table on Base.metadata as a
# side effect — required before create_all()/Alembic can see them.
from sentinel_detect.database.models import (  # noqa: F401
    AlertRecord,
    CameraRecord,
    ConfigurationRecord,
    DetectionRecord,
    EventRecord,
    UserRecord,
)


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    try:
        return create_async_engine(
            settings.url,
            echo=settings.echo,
            pool_pre_ping=True,
            pool_size=settings.pool_size,
        )
    except TypeError:
        # Some pool classes SQLAlchemy selects by default for a given URL
        # (e.g. StaticPool, used for in-memory SQLite) don't accept
        # `pool_size` at all — fall back to the engine's own default
        # pooling rather than crashing startup over a setting that
        # genuinely doesn't apply to this URL.
        return create_async_engine(settings.url, echo=settings.echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Create any missing tables. Idempotent — safe to call on every startup.

    This is the zero-setup dev path (matches SQLite being the default
    database). Production deployments, especially against Postgres, should
    manage schema changes with `alembic upgrade head` instead (see
    `migrations/`) so schema evolution is tracked and reversible.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
