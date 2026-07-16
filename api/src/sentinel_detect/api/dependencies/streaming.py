"""FastAPI dependency provider for the stream manager.

Built once in `main.py`'s lifespan and stashed on `app.state`; this
dependency just retrieves it per-request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from sentinel_detect.streaming import StreamManager


def get_stream_manager(request: Request) -> StreamManager:
    manager: StreamManager = request.app.state.stream_manager
    return manager


StreamManagerDep = Annotated[StreamManager, Depends(get_stream_manager)]
