from __future__ import annotations

from pathlib import Path

import pytest

import execution.headless_paths as headless_paths


_RUNTIME_ENV_NAMES = (
    "BUSINESAIOS_HEADLESS_ROOT",
    "BUSINESAIOS_DATA_DIR",
    "APP_RUNTIME_DATA_DIR",
    "BAIOS_DATA_DIR",
    "DATA_DIR",
)


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _RUNTIME_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_explicit_headless_root_remains_strongest_override(monkeypatch, tmp_path) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(headless_paths, "_is_test_process", lambda: False)
    explicit = tmp_path / "explicit-headless"
    shared = tmp_path / "shared-runtime"
    monkeypatch.setenv("BUSINESAIOS_HEADLESS_ROOT", str(explicit))
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(shared))

    paths = headless_paths.build_headless_runtime_paths()

    assert paths.root_dir == explicit


@pytest.mark.parametrize(
    "env_name",
    (
        "BUSINESAIOS_DATA_DIR",
        "APP_RUNTIME_DATA_DIR",
        "BAIOS_DATA_DIR",
        "DATA_DIR",
    ),
)
def test_production_shared_runtime_envs_resolve_headless_state(monkeypatch, tmp_path, env_name) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(headless_paths, "_is_test_process", lambda: False)
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv(env_name, str(runtime_root))

    paths = headless_paths.build_headless_runtime_paths()

    assert paths.root_dir == runtime_root
    assert paths.headless_baseline_history_dir == runtime_root / "headless_baseline_history"


def test_canonical_data_dir_wins_over_compatibility_runtime_envs(monkeypatch, tmp_path) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(headless_paths, "_is_test_process", lambda: False)
    canonical = tmp_path / "canonical"
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(canonical))
    monkeypatch.setenv("APP_RUNTIME_DATA_DIR", str(tmp_path / "app-runtime"))
    monkeypatch.setenv("BAIOS_DATA_DIR", str(tmp_path / "baios-runtime"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "legacy-runtime"))

    paths = headless_paths.build_headless_runtime_paths()

    assert paths.root_dir == canonical


def test_test_process_keeps_isolated_runtime_fallback(monkeypatch) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(headless_paths, "_is_test_process", lambda: True)
    monkeypatch.setenv("APP_RUNTIME_DATA_DIR", "/var/lib/businesaios/runtime")

    paths = headless_paths.build_headless_runtime_paths()

    assert paths.root_dir == Path(".runtime")


@pytest.mark.parametrize(
    "unit_path",
    (
        Path("deploy/systemd/businesaios-api.service"),
        Path("deploy/systemd/businesaios-worker.service"),
    ),
)
def test_core_systemd_units_bind_headless_state_to_shared_runtime_root(unit_path) -> None:
    unit = unit_path.read_text(encoding="utf-8")

    assert "WorkingDirectory=/opt/businesaios" in unit
    assert "Environment=BUSINESAIOS_DATA_DIR=/var/lib/businesaios/runtime" in unit
    assert "Environment=APP_RUNTIME_DATA_DIR=/var/lib/businesaios/runtime" in unit
