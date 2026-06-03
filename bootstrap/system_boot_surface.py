from __future__ import annotations

"""Final owner for system boot surface."""

from dataclasses import dataclass
from collections.abc import Mapping

from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
from bootstrap.app_boot_result import AppBootResult
from bootstrap.app_boot_surface import AppBootSurface, build_app_boot_surface
from bootstrap.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from bootstrap.runtime_boot import RuntimeBootSurface
from bootstrap.security_boot_surface import SecurityBootSurface, build_security_boot_surface
from entrypoints.api.fastapi_app_factory import create_fastapi_app

CANON_SYSTEM_BOOT_SURFACE_FINAL_OWNER = True
CANON_SYSTEM_BOOT_SURFACE = True
CANON_SYSTEM_BOOT_SURFACE_INTERNAL_SUPPORT = True
CANON_SYSTEM_BOOT_SURFACE_NO_PUBLIC_ENTRYPOINT = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


@dataclass(frozen=True)
class SystemBootSurface:
    app_boot_surface: AppBootSurface
    dependency_container: FastAPIDependencyContainer
    http_app: object
    config_surface: BootstrapConfigSurface
    security_surface: SecurityBootSurface

    @property
    def result(self) -> AppBootResult:
        return self.app_boot_surface.result

    def snapshot(self) -> dict[str, object]:
        return {
            "startup_events": self.app_boot_surface.startup_events,
            "runtime_service_names": self.app_boot_surface.runtime_service_names,
            "http_app_type": type(self.http_app).__name__,
            "dependency_container_type": type(self.dependency_container).__name__,
            "decision_application_type": type(self.app_boot_surface.result.decision_application).__name__,
            "config": self.config_surface.snapshot(),
            "security": self.security_surface.snapshot(),
        }


def build_system_boot_surface(
    *,
    config_surface: BootstrapConfigSurface | None = None,
    runtime_surface: RuntimeBootSurface | None = None,
    security_surface: SecurityBootSurface | None = None,
    shared_observability: Mapping[str, object] | None = None,
) -> SystemBootSurface:
    resolved_config_surface = config_surface or build_bootstrap_config_surface()
    resolved_security_surface = security_surface or (runtime_surface.security_surface if runtime_surface is not None else build_security_boot_surface(config_surface=resolved_config_surface))
    app_boot_surface = build_app_boot_surface(config_surface=resolved_config_surface)
    resolved_shared = dict(shared_observability or {})
    if runtime_surface is not None:
        resolved_shared = runtime_surface.shared_runtime_payload() | resolved_shared
    else:
        resolved_shared = resolved_security_surface.shared_runtime_payload() | resolved_shared
    dependency_container = FastAPIDependencyContainer(
        boot_result=app_boot_surface.result,
        config_surface=resolved_config_surface,
        shared_observability=resolved_shared,
    )
    http_app = create_fastapi_app(
        application_service=app_boot_surface.result.decision_application,
        dependency_container=dependency_container,
    )
    return SystemBootSurface(
        app_boot_surface=app_boot_surface,
        dependency_container=dependency_container,
        http_app=http_app,
        config_surface=resolved_config_surface,
        security_surface=resolved_security_surface,
    )


__all__ = ["CANON_SYSTEM_BOOT_SURFACE_FINAL_OWNER", "SystemBootSurface", "build_system_boot_surface"]
