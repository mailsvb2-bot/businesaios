from __future__ import annotations

"""Compatibility shim. Final owner: bootstrap.app_boot_surface."""

from bootstrap.app_boot_observability import AppBootObservability
from bootstrap.app_boot_result import AppBootResult
from bootstrap.app_boot_surface import AppBootSurface
from bootstrap.app_boot_surface import build_app_boot_surface as _build_app_boot_surface
from bootstrap.bootstrap_config_surface import BootstrapConfigSurface
from bootstrap.runtime_integration import RuntimeIntegration

CANON_LEGACY_BOOTSTRAP_SHIM = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"
CANON_APP_BOOT_SURFACE_OWNER = True
CANON_APP_BOOT_SURFACE_NO_RUNTIME_ASSEMBLY = True
CANON_APP_BOOT_SURFACE_DIRECT_BOOTSTRAP_IMPORTS = True


def build_app_boot_surface(
    *,
    runtime_integration: RuntimeIntegration | None = None,
    observability: AppBootObservability | None = None,
    config_surface: BootstrapConfigSurface | None = None,
) -> AppBootSurface:
    return _build_app_boot_surface(
        runtime_integration=runtime_integration,
        observability=observability,
        config_surface=config_surface,
    )


__all__ = ["AppBootResult", "AppBootObservability", "AppBootSurface", "build_app_boot_surface"]
