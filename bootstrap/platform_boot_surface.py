from __future__ import annotations

"""Final owner for platform boot surface."""

from dataclasses import dataclass

from bootstrap.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from bootstrap.runtime_boot import RuntimeBootSurface, build_runtime_boot_surface
from bootstrap.security_boot_surface import SecurityBootSurface, build_security_boot_surface
from bootstrap.system_boot_surface import SystemBootSurface, build_system_boot_surface
from boot.observability_boot import build_observability_surface

CANON_PLATFORM_BOOT_SURFACE_FINAL_OWNER = True
CANON_PLATFORM_BOOT_SURFACE = True
CANON_PLATFORM_BOOT_SURFACE_INTERNAL_SUPPORT = True
CANON_PLATFORM_BOOT_SURFACE_NO_PUBLIC_ENTRYPOINT = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


@dataclass(frozen=True)
class PlatformBootSurface:
    config_surface: BootstrapConfigSurface
    system_surface: SystemBootSurface
    runtime_surface: RuntimeBootSurface

    @property
    def app_boot_surface(self):
        return self.system_surface.app_boot_surface

    @property
    def dependency_container(self):
        return self.system_surface.dependency_container

    @property
    def http_app(self):
        return self.system_surface.http_app

    @property
    def result(self):
        return self.system_surface.result

    def snapshot(self) -> dict[str, object]:
        return {
            "config": self.config_surface.snapshot(),
            "system": self.system_surface.snapshot(),
            "runtime": self.runtime_surface.observability_snapshot(),
            "security": self.runtime_surface.security_surface.snapshot(),
        }


def build_platform_boot_surface(*, config_surface: BootstrapConfigSurface | None = None) -> PlatformBootSurface:
    resolved_config_surface = config_surface or build_bootstrap_config_surface()
    observability_surface = build_observability_surface(config_surface=resolved_config_surface)
    security_surface = build_security_boot_surface(config_surface=resolved_config_surface)
    runtime_surface = build_runtime_boot_surface(
        config_surface=resolved_config_surface,
        observability_surface=observability_surface,
        security_surface=security_surface,
    )
    system_surface = build_system_boot_surface(
        config_surface=resolved_config_surface,
        runtime_surface=runtime_surface,
        security_surface=security_surface,
    )
    return PlatformBootSurface(
        config_surface=resolved_config_surface,
        system_surface=system_surface,
        runtime_surface=runtime_surface,
    )


__all__ = ["CANON_PLATFORM_BOOT_SURFACE_FINAL_OWNER", "PlatformBootSurface", "build_platform_boot_surface"]
