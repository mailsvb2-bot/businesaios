from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.platform_boot_surface import build_platform_boot_surface
from boot.system_boot_surface import build_system_boot_surface


def test_platform_boot_surface_reuses_single_config_surface() -> None:
    config = build_bootstrap_config_surface()
    platform = build_platform_boot_surface(config_surface=config)
    assert platform.config_surface is config
    assert platform.system_surface.config_surface is config
    assert platform.runtime_surface.config_surface is config
    assert platform.dependency_container.config_surface is config


def test_platform_boot_surface_matches_explicit_system_surface_result() -> None:
    config = build_bootstrap_config_surface()
    system = build_system_boot_surface(config_surface=config)
    platform = build_platform_boot_surface(config_surface=config)
    assert type(platform.result) is type(system.result)
    assert type(platform.http_app).__name__ == type(system.http_app).__name__
