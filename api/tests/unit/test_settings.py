import pytest

from sentinel_detect.config.settings import (
    BUILTIN_DETECTOR_KEYS,
    AppSettings,
    get_settings,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings_declare_every_builtin_detector() -> None:
    settings = AppSettings(_env_file=None)

    assert set(settings.detectors) == set(BUILTIN_DETECTOR_KEYS)


def test_default_settings_enable_only_coco_covered_detectors() -> None:
    # weapon/fire/smoke/ppe need fine-tuned weights nobody ships for free,
    # so they default to disabled; person/vehicle/animal run on stock COCO
    # weights and default to enabled.
    settings = AppSettings(_env_file=None)

    assert settings.enabled_detector_keys() == ["animal", "person", "vehicle"]
    for key in ("weapon", "fire", "smoke", "ppe"):
        assert settings.detectors[key].enabled is False


def test_disabling_a_detector_removes_it_from_enabled_keys() -> None:
    settings = AppSettings(_env_file=None)
    settings.detectors["person"].enabled = False

    assert "person" not in settings.enabled_detector_keys()
    assert "vehicle" in settings.enabled_detector_keys()


def test_enabling_a_detector_adds_it_to_enabled_keys() -> None:
    settings = AppSettings(_env_file=None)
    settings.detectors["weapon"].enabled = True

    assert "weapon" in settings.enabled_detector_keys()


def test_env_var_overrides_nested_detector_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_DETECTORS__WEAPON__CONFIDENCE_THRESHOLD", "0.9")

    settings = AppSettings(_env_file=None)

    assert settings.detectors["weapon"].confidence_threshold == 0.9


def test_env_var_overrides_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_DATABASE__URL", "postgresql+asyncpg://x/y")

    settings = AppSettings(_env_file=None)

    assert settings.database.url == "postgresql+asyncpg://x/y"


def test_get_settings_is_memoized() -> None:
    assert get_settings() is get_settings()
