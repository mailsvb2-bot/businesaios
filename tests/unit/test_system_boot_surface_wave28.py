from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.http_boot_surface import build_http_boot_surface
from boot.system_boot_surface import build_system_boot_surface


def test_http_boot_surface_reuses_explicit_system_surface() -> None:
    config = build_bootstrap_config_surface()
    system_surface = build_system_boot_surface(config_surface=config)
    http_surface = build_http_boot_surface(system_surface=system_surface)
    assert http_surface.app_boot_surface is system_surface.app_boot_surface
    assert http_surface.dependency_container is system_surface.dependency_container
    assert http_surface.config_surface is config
