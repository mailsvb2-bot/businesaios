from __future__ import annotations

"""Final owner for HTTP boot surface."""

from dataclasses import dataclass

from bootstrap.app_boot_surface import AppBootSurface
from bootstrap.bootstrap_config_surface import BootstrapConfigSurface
from bootstrap.system_boot_surface import SystemBootSurface
from adapters.api.fastapi.dependencies import FastAPIDependencyContainer

CANON_HTTP_BOOT_SURFACE_FINAL_OWNER = True
CANON_HTTP_BOOT_SURFACE = True
CANON_HTTP_BOOT_SURFACE_INTERNAL_SUPPORT = True
CANON_HTTP_BOOT_SURFACE_NO_RUNTIME_ASSEMBLY = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


@dataclass(frozen=True)
class HttpBootSurface:
    app_boot_surface: AppBootSurface
    dependency_container: FastAPIDependencyContainer
    http_app: object
    config_surface: BootstrapConfigSurface

    def snapshot(self) -> dict[str, object]:
        return {
            "startup_events": self.app_boot_surface.startup_events,
            "runtime_service_names": self.app_boot_surface.runtime_service_names,
            "http_app_type": type(self.http_app).__name__,
            "dependency_container_type": type(self.dependency_container).__name__,
            "config": self.config_surface.snapshot(),
        }


def build_http_boot_surface(
    *,
    system_surface: SystemBootSurface | None = None,
    config_surface: BootstrapConfigSurface | None = None,
) -> HttpBootSurface:
    if system_surface is None:
        from bootstrap.platform_boot_contract import build_validated_platform_boot_surface
        system_surface = build_validated_platform_boot_surface(config_surface=config_surface).system_surface
    return HttpBootSurface(
        app_boot_surface=system_surface.app_boot_surface,
        dependency_container=system_surface.dependency_container,
        http_app=system_surface.http_app,
        config_surface=system_surface.config_surface,
    )


__all__ = ["CANON_HTTP_BOOT_SURFACE_FINAL_OWNER", "HttpBootSurface", "build_http_boot_surface"]
