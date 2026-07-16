"""Generic plugin registry.

This is the mechanism that lets new detectors, tracker backends, event rules,
alert channels, and storage backends be added to SENTINEL Detect without
modifying any core code: a module registers a concrete implementation under a
string key at import time, and callers resolve implementations by key from
configuration at runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from sentinel_detect.core.exceptions import RegistryError


class Registry[T]:
    """A named collection of factories for a plugin interface `T`.

    Usage:
        detector_registry: Registry[BaseDetector] = Registry("detector")

        @detector_registry.register("person")
        class PersonDetector(BaseDetector):
            ...

        detector_cls = detector_registry.get("person")
    """

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, key: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Class/function decorator that registers a factory under `key`."""

        def decorator(factory: Callable[..., T]) -> Callable[..., T]:
            if key in self._factories:
                raise RegistryError(
                    f"{self._kind} '{key}' is already registered to "
                    f"{self._factories[key]!r}"
                )
            self._factories[key] = factory
            return factory

        return decorator

    def get(self, key: str) -> Callable[..., T]:
        try:
            return self._factories[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._factories)) or "<none>"
            raise RegistryError(
                f"unknown {self._kind} '{key}'. Available: {available}"
            ) from exc

    def create(self, key: str, /, *args: object, **kwargs: object) -> T:
        """Resolve `key` and instantiate it in one step."""
        return self.get(key)(*args, **kwargs)

    def __contains__(self, key: str) -> bool:
        return key in self._factories

    def __iter__(self) -> Iterator[str]:
        return iter(self._factories)

    def keys(self) -> list[str]:
        return sorted(self._factories)
