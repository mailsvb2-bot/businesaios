from __future__ import annotations
"""Transition bridge for narrow application boot entrypoints.
This file keeps older imports working and must not grow into an alternative
sovereign runtime owner. The canonical public bootstrap surface is
``bootstrap.app_boot_surface``.
"""

from typing import Any

CANON_APP_BOOT_PUBLIC_API = True
CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_APP_PUBLIC_API_DIRECT_SURFACE_DELEGATION = True
CANON_APP_PUBLIC_API_DIRECT_BOOTSTRAP_SURFACE = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"

__all__ = [
    "CANON_APP_BOOT_PUBLIC_API",
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANON_APP_PUBLIC_API_DIRECT_SURFACE_DELEGATION",
    "CANON_APP_PUBLIC_API_DIRECT_BOOTSTRAP_SURFACE",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "boot_application",
    "build_app_boot_surface",
]


def boot_application(*args: Any, **kwargs: Any):
    from bootstrap.app_boot_surface import build_app_boot_surface as _build_app_boot_surface

    return _build_app_boot_surface(*args, **kwargs).result


def build_app_boot_surface(*args: Any, **kwargs: Any):
    from bootstrap.app_boot_surface import build_app_boot_surface as _build_app_boot_surface

    return _build_app_boot_surface(*args, **kwargs)
