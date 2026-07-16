import pytest

from sentinel_detect.core.exceptions import RegistryError
from sentinel_detect.core.registry import Registry


class Shape:
    pass


class Circle(Shape):
    pass


def test_register_and_get_returns_the_same_factory() -> None:
    registry: Registry[Shape] = Registry("shape")
    registry.register("circle")(Circle)

    assert registry.get("circle") is Circle


def test_register_is_usable_as_a_decorator() -> None:
    registry: Registry[Shape] = Registry("shape")

    @registry.register("circle")
    class DecoratedCircle(Shape):
        pass

    assert registry.get("circle") is DecoratedCircle


def test_create_instantiates_the_registered_factory() -> None:
    registry: Registry[Shape] = Registry("shape")
    registry.register("circle")(Circle)

    instance = registry.create("circle")

    assert isinstance(instance, Circle)


def test_get_unknown_key_raises_registry_error_listing_available_keys() -> None:
    registry: Registry[Shape] = Registry("shape")
    registry.register("circle")(Circle)

    with pytest.raises(RegistryError, match="circle"):
        registry.get("square")


def test_duplicate_registration_raises_registry_error() -> None:
    registry: Registry[Shape] = Registry("shape")
    registry.register("circle")(Circle)

    with pytest.raises(RegistryError):
        registry.register("circle")(Circle)


def test_contains_and_keys() -> None:
    registry: Registry[Shape] = Registry("shape")
    registry.register("circle")(Circle)

    assert "circle" in registry
    assert "square" not in registry
    assert registry.keys() == ["circle"]


def test_iterating_a_registry_yields_its_registered_keys() -> None:
    registry: Registry[Shape] = Registry("shape")
    registry.register("circle")(Circle)
    registry.register("square")(Shape)

    assert set(registry) == {"circle", "square"}
