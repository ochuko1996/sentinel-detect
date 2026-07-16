"""Exception hierarchy for SENTINEL Detect.

All exceptions raised by the platform derive from SentinelError so that API
middleware and callers can catch the platform's errors as a single family
while still discriminating on the specific subclass when needed.
"""

from __future__ import annotations


class SentinelError(Exception):
    """Base class for all SENTINEL Detect errors."""


class ConfigurationError(SentinelError):
    """Raised when application configuration is missing or invalid."""


class RegistryError(SentinelError):
    """Raised for plugin registration/lookup failures (unknown or duplicate keys)."""


class ModelLoadError(SentinelError):
    """Raised when an inference model fails to load."""


class InferenceError(SentinelError):
    """Raised when model inference fails at runtime."""


class DetectorError(SentinelError):
    """Raised when a detector fails to process a frame."""


class TrackingError(SentinelError):
    """Raised when the object tracker fails to update state."""


class EventRuleError(SentinelError):
    """Raised when an event rule fails to evaluate."""


class AlertDeliveryError(SentinelError):
    """Raised when an alert channel fails to deliver an alert."""


class StorageError(SentinelError):
    """Raised when reading from or writing to a storage backend fails."""


class VideoSourceError(SentinelError):
    """Raised when a video/image input source cannot be opened or read."""


class RepositoryError(SentinelError):
    """Raised when a database repository operation fails."""


class NotFoundError(SentinelError):
    """Raised when a requested entity does not exist."""


class AuthenticationError(SentinelError):
    """Raised when credentials are missing or invalid."""


class AuthorizationError(SentinelError):
    """Raised when an authenticated principal lacks permission for an action."""
