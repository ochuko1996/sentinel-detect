"""FastAPI dependency providing a per-request `AsyncSession`.

The session factory is built once in `main.py`'s lifespan and stashed on
`app.state`; this dependency opens one session per request and closes it
when the request finishes (whether it commits, raises, or is cancelled).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
