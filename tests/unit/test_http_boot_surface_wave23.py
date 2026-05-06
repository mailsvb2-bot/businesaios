from boot.http_boot_surface import build_http_boot_surface
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer


def test_http_boot_surface_builds_app_and_shared_container() -> None:
    surface = build_http_boot_surface()
    assert isinstance(surface.dependency_container, FastAPIDependencyContainer)
    snapshot = surface.snapshot()
    assert snapshot["http_app_type"] == "FastAPI"
    assert "app_boot_completed" in snapshot["startup_events"]
    assert surface.dependency_container.boot_result is surface.app_boot_surface.result
