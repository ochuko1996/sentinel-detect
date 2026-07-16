"""File storage port (event evidence, snapshots, thumbnails).

Concrete backends (local filesystem now; S3/GCS-compatible object storage
later) implement this without any other layer needing to know which one is
active — the API/services layers only ever hold a `BaseStorageBackend`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel_detect.core.registry import Registry


class BaseStorageBackend(ABC):
    """Port for persisting and retrieving binary evidence artifacts."""

    @abstractmethod
    async def save(self, key: str, data: bytes, *, content_type: str) -> str:
        """Persist `data` under `key` and return a URI that `get`/`delete` accept."""

    @abstractmethod
    async def get(self, uri: str) -> bytes:
        """Retrieve previously saved data. Raise `NotFoundError` if absent."""

    @abstractmethod
    async def delete(self, uri: str) -> None:
        """Remove a previously saved artifact. No-op if already absent."""

    @abstractmethod
    async def exists(self, uri: str) -> bool:
        """Whether `uri` currently refers to a stored artifact."""


storage_backend_registry: Registry[BaseStorageBackend] = Registry("storage_backend")
