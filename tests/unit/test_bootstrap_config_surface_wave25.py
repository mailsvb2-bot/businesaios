from __future__ import annotations

from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.system_boot_surface import build_system_boot_surface
from boot.http_boot_surface import build_http_boot_surface
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from observability.metrics import InMemoryMetrics


class _Service:
    def execute_action(self, action):
        return {"status": "ok", "action_type": action.action_type, "reason": "executed"}


class _RuntimeStub:
    metrics = InMemoryMetrics()


class _BootResultStub:
    runtime = _RuntimeStub()
    decision_application = _Service()
    startup_report = ()


def test_bootstrap_config_surface_is_canonical_for_dependency_container(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("BUSINESAIOS_OBSERVABILITY_DATA_DIR", str(tmp_path / "observability-data"))
    monkeypatch.setenv("BUSINESAIOS_OBSERVABILITY_STORE_MODE", "persistent")

    surface = build_bootstrap_config_surface()
    container = FastAPIDependencyContainer(boot_result=_BootResultStub())

    assert container.config_snapshot() == surface.snapshot()
    assert container._default_api_idempotency_path() == surface.api_idempotency_path
    assert surface.observability_store_mode == "persistent"


def test_system_and_http_boot_surfaces_share_config_snapshot(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("BUSINESAIOS_OBSERVABILITY_DATA_DIR", str(tmp_path / "observability-data"))
    monkeypatch.setenv("BUSINESAIOS_OBSERVABILITY_STORE_MODE", "persistent")

    system_surface = build_system_boot_surface()
    http_surface = build_http_boot_surface()

    assert system_surface.snapshot()["config"] == http_surface.snapshot()["config"]
    assert system_surface.config_surface.snapshot()["observability_store_mode"] == "persistent"


def test_system_surface_threads_single_config_surface_into_app_and_container(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("BUSINESAIOS_OBSERVABILITY_DATA_DIR", str(tmp_path / "observability-data"))
    system_surface = build_system_boot_surface()

    assert system_surface.app_boot_surface.config_surface is system_surface.config_surface
    assert system_surface.dependency_container.config_surface is system_surface.config_surface
    assert system_surface.app_boot_surface.startup_snapshot()["config"] == system_surface.config_surface.snapshot()
