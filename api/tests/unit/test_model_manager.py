from pathlib import Path

import pytest

from sentinel_detect.config.settings import ModelSettings
from sentinel_detect.core.exceptions import ConfigurationError
from sentinel_detect.models.manager import ModelManager


def test_get_unknown_model_key_raises_configuration_error(tmp_path: Path) -> None:
    settings = ModelSettings(weights_dir=tmp_path, weights={})
    manager = ModelManager(settings)

    with pytest.raises(ConfigurationError, match="unknown_key"):
        manager.get("unknown_key")


def test_loaded_models_starts_empty() -> None:
    settings = ModelSettings()
    manager = ModelManager(settings)

    assert manager.loaded_models() == {}
