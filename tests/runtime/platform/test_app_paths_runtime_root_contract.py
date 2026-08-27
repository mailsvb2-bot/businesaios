from __future__ import annotations

from pathlib import Path

import pytest

from runtime.platform import app_paths

_RUNTIME_ENVS = (
    "BUSINESAIOS_HOME",
    "BUSINESAIOS_DATA_DIR",
    "APP_RUNTIME_DATA_DIR",
    "BAIOS_DATA_DIR",
    "DATA_DIR",
)


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _RUNTIME_ENVS:
        monkeypatch.delenv(name, raising=False)


def test_runtime_data_dir_uses_systemd_shared_runtime_root(monkeypatch, tmp_path) -> None:
    _clear_runtime_env(monkeypatch)
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("APP_RUNTIME_DATA_DIR", str(runtime_root))
    monkeypatch.setenv("HOME", str(tmp_path / "unwritable-deploy-home"))

    chosen = app_paths.runtime_data_dir()

    assert chosen == runtime_root.resolve()
    assert chosen.is_dir()


def test_legacy_businesaios_home_remains_strongest_app_override(monkeypatch, tmp_path) -> None:
    _clear_runtime_env(monkeypatch)
    legacy_override = tmp_path / "legacy-home"
    monkeypatch.setenv("BUSINESAIOS_HOME", str(legacy_override))
    monkeypatch.setenv("APP_RUNTIME_DATA_DIR", str(tmp_path / "shared-runtime"))

    assert app_paths.runtime_data_dir() == legacy_override.resolve()


def test_telegram_systemd_contract_exposes_shared_runtime_root() -> None:
    unit = Path("deploy/systemd/businesaios-connector-telegram.service").read_text(encoding="utf-8")

    assert "Environment=APP_RUNTIME_DATA_DIR=/var/lib/businesaios/runtime" in unit
    assert "Environment=BAIOS_DATA_DIR=/var/lib/businesaios/runtime" in unit
    assert "Environment=DATA_DIR=/var/lib/businesaios/runtime" in unit
    assert "ExecStart=/usr/bin/env APP_PROFILE=telegram DATA_DIR=/var/lib/businesaios/runtime " in unit
