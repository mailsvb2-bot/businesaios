from __future__ import annotations

from scripts.ci.step_production_boot import (
    CANON_PRODUCTION_BOOT_ENV_DRIFT_GUARD,
    LEGACY_ENV_KEYS,
    _legacy_env_keys_present,
)


def test_production_boot_env_drift_guard_is_enabled() -> None:
    assert CANON_PRODUCTION_BOOT_ENV_DRIFT_GUARD is True
    assert "METRO_DB_ENGINE" in LEGACY_ENV_KEYS
    assert "STORAGE_DB_ENGINE" in LEGACY_ENV_KEYS


def test_legacy_env_keys_present_reports_only_non_blank_legacy_keys() -> None:
    env = {
        "METRO_DB_ENGINE": "postgres",
        "STORAGE_DB_ENGINE": "",
        "STORAGE_BACKEND": "postgres",
    }

    assert _legacy_env_keys_present(env) == ["METRO_DB_ENGINE"]


def test_legacy_env_keys_present_allows_canonical_keys() -> None:
    env = {
        "STORAGE_BACKEND": "postgres",
        "POSTGRES_RUNTIME_ENABLED": "1",
        "POSTGRES_EVENT_STORE_ENABLED": "1",
    }

    assert _legacy_env_keys_present(env) == []
