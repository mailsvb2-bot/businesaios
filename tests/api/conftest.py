from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolate_api_runtime_artifacts(tmp_path, monkeypatch):
    """Keep API smoke/router/factory tests from leaking mutable runtime state into repo root."""

    runtime_dir = tmp_path / "runtime"
    data_dir = tmp_path / "data"

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("BAIOS_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("BUSINESAIOS_RUNTIME_DIR", str(runtime_dir))

    shutil.rmtree(ROOT / ".runtime", ignore_errors=True)
    yield
    shutil.rmtree(ROOT / ".runtime", ignore_errors=True)
