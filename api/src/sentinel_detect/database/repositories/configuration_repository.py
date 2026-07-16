"""Repository for `ConfigurationEntry` <-> `ConfigurationRecord`.

Backs `GET/POST /config` (`api/routers/config.py`). Keyed by `key: str`,
not a UUID.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.core.entities.configuration import ConfigurationEntry
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.database.models.configuration import ConfigurationRecord


class ConfigurationRepository(Repository[ConfigurationEntry, str]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: str) -> ConfigurationEntry | None:
        record = await self._session.get(ConfigurationRecord, entity_id)
        return self._to_entity(record) if record is not None else None

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[ConfigurationEntry]:
        stmt = (
            select(ConfigurationRecord)
            .order_by(ConfigurationRecord.key)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def create(self, entity: ConfigurationEntry) -> ConfigurationEntry:
        record = self._to_record(entity)
        self._session.add(record)
        await self._session.flush()
        return entity

    async def update(self, entity: ConfigurationEntry) -> ConfigurationEntry:
        record = await self._session.get(ConfigurationRecord, entity.key)
        if record is None:
            raise NotFoundError(f"configuration '{entity.key}' does not exist")
        record.value = entity.value
        record.updated_at = entity.updated_at
        await self._session.flush()
        return entity

    async def delete(self, entity_id: str) -> None:
        record = await self._session.get(ConfigurationRecord, entity_id)
        if record is None:
            raise NotFoundError(f"configuration '{entity_id}' does not exist")
        await self._session.delete(record)
        await self._session.flush()

    @staticmethod
    def _to_entity(record: ConfigurationRecord) -> ConfigurationEntry:
        return ConfigurationEntry(key=record.key, value=record.value, updated_at=record.updated_at)

    @staticmethod
    def _to_record(entity: ConfigurationEntry) -> ConfigurationRecord:
        return ConfigurationRecord(key=entity.key, value=entity.value, updated_at=entity.updated_at)
