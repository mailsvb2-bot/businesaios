from __future__ import annotations

from importlib import import_module

from bootstrap.app_boot_result import AppBootResult

CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_APP_BOOT_THIN_SHIM = True
CANON_APP_BOOT_NO_RUNTIME_ASSEMBLY = True
CANON_APP_BOOT_DIRECT_OWNER_DELEGATION = True
CANON_APP_BOOT_NO_EAGER_RUNTIME_INTEGRATION_IMPORT = True
CANON_APP_BOOT_DIRECT_BOOTSTRAP_APP_BOOT = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"
# RuntimeIntegration remains the canonical runtime assembly boundary; this shim delegates instead of building runtime directly.


def _load_attr(module_name: str, attr_name: str):
    return getattr(import_module(module_name), attr_name)


def boot_application() -> AppBootResult:
    build_app_boot_surface = _load_attr("bootstrap.app_boot_surface", "build_app_boot_surface")
    return build_app_boot_surface().result
