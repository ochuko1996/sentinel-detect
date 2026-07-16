"""Generic data-access port for the database layer (Phase 6).

One `Repository[T, ID]` shape covers events, detections, cameras, users, and
config records; concrete SQLAlchemy repositories parametrize this per entity.
Keeping the interface here (not in `database/`) means services depend on the
abstraction, not on SQLAlchemy or any specific engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Repository[T, ID](ABC):
    """Port for CRUD + listing access to persisted entities of type `T`."""

    @abstractmethod
    async def get(self, entity_id: ID) -> T | None:
        """Fetch by primary key, or None if it does not exist."""

    @abstractmethod
    async def list(self, *, offset: int = 0, limit: int = 100) -> list[T]:
        """Fetch a page of entities, most-recent-first."""

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Persist a new entity and return it (with any server-assigned fields set)."""

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Persist changes to an existing entity and return the updated form."""

    @abstractmethod
    async def delete(self, entity_id: ID) -> None:
        """Remove an entity by primary key. Raise `NotFoundError` if absent."""
