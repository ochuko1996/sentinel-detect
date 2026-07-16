"""Custom SQLAlchemy column types shared by the ORM models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """A timezone-aware `DateTime` that round-trips correctly on SQLite.

    SQLite has no native datetime type: SQLAlchemy's `DateTime(timezone=True)`
    stores the value correctly but SQLite always returns a naive `datetime`
    on read (there's nowhere to persist tzinfo). Every datetime this app
    produces is UTC by convention (`datetime.now(UTC)`), so this type
    re-attaches UTC tzinfo on read rather than silently handing callers a
    naive datetime that compares unequal to the original timezone-aware
    value. Postgres's native `timestamptz` doesn't need this, but applying
    it universally keeps model code identical across both backends.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return value
