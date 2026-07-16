"""Tests that `DatabaseSettings.pool_size` (configured since Phase 6, unused
until Phase 9) is genuinely passed through to the real async engine."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sentinel_detect.config.settings import DatabaseSettings
from sentinel_detect.database.engine import create_engine


def test_pool_size_setting_is_applied_to_a_file_based_engine(tmp_path: Path) -> None:
    settings = DatabaseSettings(url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", pool_size=7)
    engine = create_engine(settings)

    try:
        assert engine.pool.size() == 7
    finally:
        asyncio.run(engine.dispose())


def test_engine_construction_falls_back_gracefully_when_pool_size_is_unsupported() -> None:
    # In-memory SQLite defaults to StaticPool, which doesn't accept
    # `pool_size` at all — construction must degrade instead of raising.
    settings = DatabaseSettings(url="sqlite+aiosqlite:///:memory:", pool_size=7)

    engine = create_engine(settings)

    asyncio.run(engine.dispose())
