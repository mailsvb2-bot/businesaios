from __future__ import annotations

import pytest

from runtime.bootstrap.environment_loader import load_bootstrap_environment
from runtime.bootstrap.startup_validator import validate_single_bootstrap_path


def test_single_bootstrap_path_rejects_legacy_entrypoints(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    env = load_bootstrap_environment(project_root=tmp_path)

    with pytest.raises(RuntimeError) as exc:
        validate_single_bootstrap_path(
            loaded_modules={
                "runtime.bootstrap.sovereign_bootstrap",
                "boot.bootstrap",
            },
            env=env,
        )

    assert "LEGACY_BOOTSTRAP_ENTRYPOINT_DETECTED" in str(exc.value)


def test_single_bootstrap_path_allows_internal_runtime_builder_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    env = load_bootstrap_environment(project_root=tmp_path)

    validate_single_bootstrap_path(
        loaded_modules={
            "runtime.bootstrap.sovereign_bootstrap",
            "runtime.bootstrap.runtime_composition_root",
            "runtime.bootstrap.runtime_builder",
        },
        env=env,
    )


def test_test_mode_disables_lock_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("BOOTSTRAP_SINGLETON_LOCK", raising=False)

    env = load_bootstrap_environment(project_root=tmp_path)

    assert env.singleton_lock_enabled is False
