"""Authentication/authorization primitives: password hashing, JWT tokens,
and rate limiting. RBAC enforcement and the API's auth dependency live in
`api/dependencies/auth.py` (they need FastAPI + the database session, which
would make this a much heavier, framework-coupled package if included here).
"""

from sentinel_detect.security.passwords import hash_password, verify_password
from sentinel_detect.security.rate_limit import RateLimitMiddleware
from sentinel_detect.security.tokens import TokenPayload, create_access_token, decode_access_token

__all__ = [
    "RateLimitMiddleware",
    "TokenPayload",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
