"""User entity for authentication/authorization. `security/tokens.py` issues
JWTs from it; `api/dependencies/auth.py` enforces RBAC on top of it."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserRole(StrEnum):
    """Role-based access control tiers."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(BaseModel, frozen=True):
    id: UUID = Field(default_factory=uuid4)
    username: str
    email: str
    hashed_password: str
    """Opaque hash string produced by `security/passwords.py` (bcrypt); this
    entity only defines the persisted shape, not the hashing scheme."""
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
