from boot.bootstrap_config_surface import build_bootstrap_config_surface
from bootstrap.runtime_boot import build_runtime_boot_surface
from bootstrap.security_boot_surface import build_security_boot_surface
from bootstrap.system_boot_surface import build_system_boot_surface


def test_security_boot_surface_builds_shared_api_security_owner_bundle() -> None:
    config = build_bootstrap_config_surface()
    surface = build_security_boot_surface(config_surface=config)
    assert surface.config_surface is config
    assert surface.api_security_owner_bundle.api_surface_guard.adapter is surface.api_security_owner_bundle.adapter


def test_runtime_and_system_boot_surfaces_share_security_owner_bundle() -> None:
    config = build_bootstrap_config_surface()
    runtime_surface = build_runtime_boot_surface(config_surface=config)
    system_surface = build_system_boot_surface(config_surface=config, runtime_surface=runtime_surface)
    assert system_surface.dependency_container.security_owner_bundle() is runtime_surface.security_surface.api_security_owner_bundle
