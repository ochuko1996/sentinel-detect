"""FastAPI dependency provider for the detection service.

The `DetectionService` instance is built once in `main.py`'s lifespan (it
owns loaded model weights) and stashed on `app.state`; this dependency just
retrieves it per-request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from sentinel_detect.services.detection_service import DetectionService


def get_detection_service(request: Request) -> DetectionService:
    service: DetectionService = request.app.state.detection_service
    return service


DetectionServiceDep = Annotated[DetectionService, Depends(get_detection_service)]
