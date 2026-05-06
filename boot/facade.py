from __future__ import annotations

"""Legacy boot facade shim.
Kept only for compatibility. Final assembly ownership lives in ``bootstrap``
and runtime process hygiene lives in ``runtime.bootstrap``.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_BOOT_FACADE_THIN_SHIM = True
CANON_BOOT_FACADE_DIRECT_OWNER_DELEGATION = True
CANON_BOOT_FACADE_NO_ASSEMBLY_OWNERSHIP = True
CANON_BOOT_FACADE_BUILT_RUNTIME_COMPAT_BRIDGE = True
CANON_BOOT_FACADE_DIRECT_BOOTSTRAP_COMPOSE_BUILD_RUNTIME = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.compose"


@dataclass(frozen=True)
class BootFacade:
    boot_application: Callable[[], Any]
    build_app_boot_surface: Callable[[], Any]
    boot_http_app: Callable[[], Any]
    build_runtime: Callable[[], object]


def _load_attr(module_name: str, attr_name: str):
    return getattr(import_module(module_name), attr_name)


def _boot_application() -> Any:
    return _load_attr("bootstrap.app_boot_surface", "build_app_boot_surface")().result


def _build_app_boot_surface() -> Any:
    return _load_attr("bootstrap.app_boot_surface", "build_app_boot_surface")()


def _boot_http_app() -> Any:
    return _load_attr("bootstrap.http_boot_surface", "build_http_boot_surface")().http_app


def _build_runtime() -> object:
    return _load_attr("bootstrap.compose", "build_runtime")()


def get_boot_facade() -> BootFacade:
    return BootFacade(
        boot_application=_boot_application,
        build_app_boot_surface=_build_app_boot_surface,
        boot_http_app=_boot_http_app,
        build_runtime=_build_runtime,
    )


__all__ = [
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANON_BOOT_FACADE_THIN_SHIM",
    "CANON_BOOT_FACADE_DIRECT_OWNER_DELEGATION",
    "CANON_BOOT_FACADE_NO_ASSEMBLY_OWNERSHIP",
    "CANON_BOOT_FACADE_BUILT_RUNTIME_COMPAT_BRIDGE",
    "CANON_BOOT_FACADE_DIRECT_BOOTSTRAP_COMPOSE_BUILD_RUNTIME",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "BootFacade",
    "get_boot_facade",
]
