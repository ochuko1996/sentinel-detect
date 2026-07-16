"""Repository for `User` <-> `UserRecord`.

Backs `POST /auth/login` (`api/routers/auth.py`) and the bootstrap-admin
creation step in `main.py`'s lifespan.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_detect.core.entities.user import User, UserRole
from sentinel_detect.core.exceptions import NotFoundError
from sentinel_detect.core.interfaces.repository import Repository
from sentinel_detect.database.models.user import UserRecord


class UserRepository(Repository[User, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> User | None:
        record = await self._session.get(UserRecord, entity_id)
        return self._to_entity(record) if record is not None else None

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(UserRecord).where(UserRecord.username == username)
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(record) if record is not None else None

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[User]:
        stmt = select(UserRecord).order_by(UserRecord.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(record) for record in result.scalars()]

    async def create(self, entity: User) -> User:
        record = self._to_record(entity)
        self._session.add(record)
        await self._session.flush()
        return entity

    async def update(self, entity: User) -> User:
        record = await self._session.get(UserRecord, entity.id)
        if record is None:
            raise NotFoundError(f"user '{entity.id}' does not exist")
        for key, value in self._to_record(entity).__dict__.items():
            if not key.startswith("_"):
                setattr(record, key, value)
        await self._session.flush()
        return entity

    async def delete(self, entity_id: UUID) -> None:
        record = await self._session.get(UserRecord, entity_id)
        if record is None:
            raise NotFoundError(f"user '{entity_id}' does not exist")
        await self._session.delete(record)
        await self._session.flush()

    @staticmethod
    def _to_entity(record: UserRecord) -> User:
        return User(
            id=record.id,
            username=record.username,
            email=record.email,
            hashed_password=record.hashed_password,
            role=UserRole(record.role),
            is_active=record.is_active,
            created_at=record.created_at,
        )

    @staticmethod
    def _to_record(entity: User) -> UserRecord:
        return UserRecord(
            id=entity.id,
            username=entity.username,
            email=entity.email,
            hashed_password=entity.hashed_password,
            role=entity.role.value,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )
