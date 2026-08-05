from boot.app_boot import boot_application
from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.http_boot import boot_http_app
from boot.http_boot_surface import build_http_boot_surface
from boot.system_boot_surface import build_system_boot_surface


def test_system_boot_surface_builds_app_and_http_from_single_owner() -> None:
    surface = build_system_boot_surface()
    snapshot = surface.snapshot()
    assert snapshot["http_app_type"] == "FastAPI"
    assert snapshot["dependency_container_type"] == "FastAPIDependencyContainer"
    assert snapshot["decision_application_type"] == type(surface.result.decision_application).__name__
    assert "runtime_services" not in snapshot
    assert snapshot["runtime_service_names"] == surface.app_boot_surface.runtime_service_names


def test_legacy_boot_shims_delegate_to_system_boot_surface() -> None:
    booted = boot_application()
    http_app = boot_http_app()
    assert hasattr(booted, "decision_application")
    assert type(http_app).__name__ == "FastAPI"


def test_http_boot_surface_reuses_explicit_system_surface() -> None:
    config = build_bootstrap_config_surface()
    system_surface = build_system_boot_surface(config_surface=config)
    http_surface = build_http_boot_surface(system_surface=system_surface)
    assert http_surface.app_boot_surface is system_surface.app_boot_surface
    assert http_surface.dependency_container is system_surface.dependency_container
    assert http_surface.config_surface is config
