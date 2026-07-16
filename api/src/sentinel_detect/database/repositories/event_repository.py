"""Repository for `Event` <-> `EventRecord`."""

from __future__ import annotations

import builtins
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.database.models.event import EventRecord


class EventRepository(Repository[Event, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> Event | None:
        record = await self._session.get(EventRecord, entity_id)
        return self._to_entity(record) if record is not None else None

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Event]:
        stmt = (
            select(EventRecord).order_by(EventRecord.timestamp.desc()).offset(offset).limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def list_by_camera(
        self, camera_id: str, *, offset: int = 0, limit: int = 100
    ) -> builtins.list[Event]:
        # builtins.list, not list: this class already defines a method named
        # `list` (above), which shadows the builtin type for annotations on
        # any method defined after it in this same class body.
        stmt = (
            select(EventRecord)
            .where(EventRecord.camera_id == camera_id)
            .order_by(EventRecord.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def create(self, entity: Event) -> Event:
        record = self._to_record(entity)
        self._session.add(record)
        await self._session.flush()
        return entity

    async def update(self, entity: Event) -> Event:
        record = await self._session.get(EventRecord, entity.id)
        if record is None:
            raise NotFoundError(f"event '{entity.id}' does not exist")
        for key, value in self._to_record(entity).__dict__.items():
            if not key.startswith("_"):
                setattr(record, key, value)
        await self._session.flush()
        return entity

    async def delete(self, entity_id: UUID) -> None:
        record = await self._session.get(EventRecord, entity_id)
        if record is None:
            raise NotFoundError(f"event '{entity_id}' does not exist")
        await self._session.delete(record)
        await self._session.flush()

    @staticmethod
    def _to_entity(record: EventRecord) -> Event:
        return Event(
            id=record.id,
            camera_id=record.camera_id,
            type=EventType(record.type),
            severity=EventSeverity(record.severity),
            rule=record.rule,
            track_ids=tuple(record.track_ids),
            region_id=record.region_id,
            message=record.message,
            metadata=record.metadata_,
            timestamp=record.timestamp,
        )

    @staticmethod
    def _to_record(entity: Event) -> EventRecord:
        return EventRecord(
            id=entity.id,
            camera_id=entity.camera_id,
            type=entity.type.value,
            severity=entity.severity.value,
            rule=entity.rule,
            track_ids=list(entity.track_ids),
            region_id=entity.region_id,
            message=entity.message,
            metadata_=entity.metadata,
            timestamp=entity.timestamp,
        )
