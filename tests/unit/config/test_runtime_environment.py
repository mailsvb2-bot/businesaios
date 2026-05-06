from __future__ import annotations

from config.runtime_environment import load_runtime_environment


def test_load_runtime_environment_normalizes_case(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "Production")
    monkeypatch.setenv("RUN_MODE", " HEADLESS ")
    monkeypatch.setenv("TENANT_ID", "tenant-42")
    env = load_runtime_environment()
    assert env.app_env == "production"
    assert env.run_mode == "headless"
    assert env.tenant_id == "tenant-42"
    assert env.is_production is True
