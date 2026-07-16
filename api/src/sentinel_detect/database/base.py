"""Declarative base every ORM model inherits from.

A single shared `Base` is what lets `Base.metadata.create_all()` (dev
convenience) and Alembic's autogenerate (`migrations/env.py`) see every
table — each model module must be imported somewhere for its table to
register on this metadata (see `database/models/__init__.py`).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
