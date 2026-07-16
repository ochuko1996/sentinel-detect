"""Repository for `Camera` <-> `CameraRecord`.

Backs Camera CRUD (`api/routers/cameras.py`) and camera lookups for
starting a live stream (`api/routers/stream.py`).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.core.entities.camera import Camera, Region, SourceType
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.database.models.camera import CameraRecord


class CameraRepository(Repository[Camera, str]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: str) -> Camera | None:
        record = await self._session.get(CameraRecord, entity_id)
        return self._to_entity(record) if record is not None else None

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Camera]:
        stmt = select(CameraRecord).order_by(CameraRecord.id).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def create(self, entity: Camera) -> Camera:
        record = self._to_record(entity)
        self._session.add(record)
        await self._session.flush()
        return entity

    async def update(self, entity: Camera) -> Camera:
        record = await self._session.get(CameraRecord, entity.id)
        if record is None:
            raise NotFoundError(f"camera '{entity.id}' does not exist")
        for key, value in self._to_record(entity).__dict__.items():
            if not key.startswith("_"):
                setattr(record, key, value)
        await self._session.flush()
        return entity

    async def delete(self, entity_id: str) -> None:
        record = await self._session.get(CameraRecord, entity_id)
        if record is None:
            raise NotFoundError(f"camera '{entity_id}' does not exist")
        await self._session.delete(record)
        await self._session.flush()

    @staticmethod
    def _to_entity(record: CameraRecord) -> Camera:
        return Camera(
            id=record.id,
            name=record.name,
            source_type=SourceType(record.source_type),
            uri=record.uri,
            enabled=record.enabled,
            enabled_detectors=tuple(record.enabled_detectors),
            regions=tuple(Region.model_validate(region) for region in record.regions),
            frame_rate_limit=record.frame_rate_limit,
            inference_size=(record.inference_width, record.inference_height),
        )

    @staticmethod
    def _to_record(entity: Camera) -> CameraRecord:
        return CameraRecord(
            id=entity.id,
            name=entity.name,
            source_type=entity.source_type.value,
            uri=entity.uri,
            enabled=entity.enabled,
            enabled_detectors=list(entity.enabled_detectors),
            regions=[region.model_dump(mode="json") for region in entity.regions],
            frame_rate_limit=entity.frame_rate_limit,
            inference_width=entity.inference_size[0],
            inference_height=entity.inference_size[1],
        )
