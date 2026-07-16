"""FastAPI dependency provider for the full detection+tracking+event pipeline.

The `PipelineService` instance is built once in `main.py`'s lifespan and
stashed on `app.state`; this dependency just retrieves it per-request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from sentinel_detect.services.pipeline_service import PipelineService


def get_pipeline_service(request: Request) -> PipelineService:
    service: PipelineService = request.app.state.pipeline_service
    return service


PipelineServiceDep = Annotated[PipelineService, Depends(get_pipeline_service)]
