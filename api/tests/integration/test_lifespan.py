"""Integration tests for main.py's lifespan: bootstrap-admin-on-startup and
graceful handling of a model that fails to warm up.

Unlike other integration tests, these build a fresh `create_app()` instance
(rather than importing the module-level `app` singleton) because they need
settings resolved with specific env vars in place — `get_settings()` is
process-memoized, so it's cleared before and after each test here to avoid
leaking a non-default cached settings object into other test files that
import the shared `app`.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sentinel_detect.config.settings import get_settings
from sentinel_detect.core.interfaces.model import RawPrediction
from sentinel_detect.main import create_app
from sentinel_detect.models.manager import ModelManager


def test_bootstrap_admin_is_created_once_and_not_duplicated_on_a_second_boot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    username = f"bootstrap-{uuid4().hex[:12]}"
    monkeypatch.setenv("SENTINEL_DATABASE__URL", f"sqlite+aiosqlite:///{tmp_path / 'boot.db'}")
    monkeypatch.setenv("SENTINEL_SECURITY__BOOTSTRAP_ADMIN_USERNAME", username)
    monkeypatch.setenv("SENTINEL_SECURITY__BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-pw-123")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            login = client.post(
                "/auth/login", data={"username": username, "password": "bootstrap-pw-123"}
            )
            assert login.status_code == 200

        # Booting again against the same now-populated database must find
        # the existing account and skip re-creating it, not fail.
        with TestClient(create_app()) as client:
            login_again = client.post(
                "/auth/login", data={"username": username, "password": "bootstrap-pw-123"}
            )
            assert login_again.status_code == 200
    finally:
        get_settings.cache_clear()


def test_startup_survives_a_model_that_fails_to_warm_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FailsToWarmUp:
        def load(self) -> None:
            pass

        def predict(self, frame: object) -> list[RawPrediction]:
            return []

        def warmup(self) -> None:
            raise RuntimeError("simulated warmup failure")

        @property
        def is_loaded(self) -> bool:
            return True

        @property
        def class_names(self) -> dict[int, str]:
            return {}

    monkeypatch.setattr(
        ModelManager, "loaded_models", lambda self: {"fake_model": _FailsToWarmUp()}
    )
    monkeypatch.setenv("SENTINEL_DATABASE__URL", f"sqlite+aiosqlite:///{tmp_path / 'warmup.db'}")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            # Startup must complete (not raise) despite the warmup failure —
            # a working /health response proves the app is actually up.
            assert client.get("/health").status_code == 200
    finally:
        get_settings.cache_clear()
