"""Repository for `Detection` <-> `DetectionRecord`."""

from __future__ import annotations

import builtins
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.core.entities.detection import Detection, DetectionClass
from sentinel_detect.core.entities.geometry import BoundingBox
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.database.models.detection import DetectionRecord


class DetectionRepository(Repository[Detection, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> Detection | None:
        record = await self._session.get(DetectionRecord, entity_id)
        return self._to_entity(record) if record is not None else None

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Detection]:
        stmt = (
            select(DetectionRecord)
            .order_by(DetectionRecord.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def list_by_camera(
        self, camera_id: str, *, offset: int = 0, limit: int = 100
    ) -> builtins.list[Detection]:
        # builtins.list, not list: this class already defines a method named
        # `list` (above), which shadows the builtin type for annotations on
        # any method defined after it in this same class body.
        stmt = (
            select(DetectionRecord)
            .where(DetectionRecord.camera_id == camera_id)
            .order_by(DetectionRecord.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def create(self, entity: Detection) -> Detection:
        record = self._to_record(entity)
        self._session.add(record)
        await self._session.flush()
        return entity

    async def update(self, entity: Detection) -> Detection:
        record = await self._session.get(DetectionRecord, entity.id)
        if record is None:
            raise NotFoundError(f"detection '{entity.id}' does not exist")
        for key, value in self._to_record(entity).__dict__.items():
            if not key.startswith("_"):
                setattr(record, key, value)
        await self._session.flush()
        return entity

    async def delete(self, entity_id: UUID) -> None:
        record = await self._session.get(DetectionRecord, entity_id)
        if record is None:
            raise NotFoundError(f"detection '{entity_id}' does not exist")
        await self._session.delete(record)
        await self._session.flush()

    @staticmethod
    def _to_entity(record: DetectionRecord) -> Detection:
        return Detection(
            id=record.id,
            camera_id=record.camera_id,
            detector=record.detector,
            label=DetectionClass(record.label),
            confidence=record.confidence,
            bbox=BoundingBox(
                x1=record.bbox_x1, y1=record.bbox_y1, x2=record.bbox_x2, y2=record.bbox_y2
            ),
            frame_width=record.frame_width,
            frame_height=record.frame_height,
            timestamp=record.timestamp,
        )

    @staticmethod
    def _to_record(entity: Detection) -> DetectionRecord:
        return DetectionRecord(
            id=entity.id,
            camera_id=entity.camera_id,
            detector=entity.detector,
            label=entity.label.value,
            confidence=entity.confidence,
            bbox_x1=entity.bbox.x1,
            bbox_y1=entity.bbox.y1,
            bbox_x2=entity.bbox.x2,
            bbox_y2=entity.bbox.y2,
            frame_width=entity.frame_width,
            frame_height=entity.frame_height,
            timestamp=entity.timestamp,
        )
