"""Password hashing via `bcrypt` directly (not `passlib`, which has had
long-standing bcrypt-version compatibility friction and is effectively
unmaintained)."""

from __future__ import annotations

import bcrypt


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (e.g. not actually a bcrypt hash) — treat as no match
        # rather than raising, so a corrupt stored value fails auth, not 500s.
        return False
