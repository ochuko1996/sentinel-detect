"""Repository for `Alert` <-> `AlertRecord`.

`AlertRecord.event_id` is a real foreign key into `events` — callers must
persist the referenced `Event` (via `EventRepository.create`) in the same
session *before* creating the `Alert` that references it, so the row exists
(even if only flushed, not yet committed) when the FK is checked.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.core.entities.alert import Alert, AlertChannelType, AlertStatus
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.database.models.alert import AlertRecord
from sentinel_detect.database.models.event import EventRecord
from sentinel_detect.database.repositories.event_repository import EventRepository


class AlertRepository(Repository[Alert, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> Alert | None:
        stmt = (
            select(AlertRecord, EventRecord)
            .join(EventRecord, AlertRecord.event_id == EventRecord.id)
            .where(AlertRecord.id == entity_id)
        )
        row = (await self._session.execute(stmt)).first()
        return self._to_entity(*row) if row is not None else None

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Alert]:
        stmt = (
            select(AlertRecord, EventRecord)
            .join(EventRecord, AlertRecord.event_id == EventRecord.id)
            .order_by(AlertRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            self._to_entity(alert_record, event_record) for alert_record, event_record in result
        ]

    async def create(self, entity: Alert) -> Alert:
        record = AlertRecord(
            id=entity.id,
            event_id=entity.event.id,
            channel=entity.channel.value,
            status=entity.status.value,
            error=entity.error,
            created_at=entity.created_at,
            delivered_at=entity.delivered_at,
        )
        self._session.add(record)
        await self._session.flush()
        return entity

    async def update(self, entity: Alert) -> Alert:
        record = await self._session.get(AlertRecord, entity.id)
        if record is None:
            raise NotFoundError(f"alert '{entity.id}' does not exist")
        record.status = entity.status.value
        record.error = entity.error
        record.delivered_at = entity.delivered_at
        await self._session.flush()
        return entity

    async def delete(self, entity_id: UUID) -> None:
        record = await self._session.get(AlertRecord, entity_id)
        if record is None:
            raise NotFoundError(f"alert '{entity_id}' does not exist")
        await self._session.delete(record)
        await self._session.flush()

    @staticmethod
    def _to_entity(alert_record: AlertRecord, event_record: EventRecord) -> Alert:
        return Alert(
            id=alert_record.id,
            event=EventRepository._to_entity(event_record),
            channel=AlertChannelType(alert_record.channel),
            status=AlertStatus(alert_record.status),
            error=alert_record.error,
            created_at=alert_record.created_at,
            delivered_at=alert_record.delivered_at,
        )
