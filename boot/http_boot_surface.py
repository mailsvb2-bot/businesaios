from __future__ import annotations

"""Compatibility shim. Final owner: bootstrap.http_boot_surface."""

from bootstrap.http_boot_surface import (
    CANON_HTTP_BOOT_SURFACE_FINAL_OWNER,
    HttpBootSurface,
    build_http_boot_surface as _build_http_boot_surface,
)

CANON_HTTP_BOOT_SURFACE = True
CANON_HTTP_BOOT_SURFACE_INTERNAL_SUPPORT = True
CANON_HTTP_BOOT_SURFACE_NO_RUNTIME_ASSEMBLY = True
CANON_HTTP_BOOT_SURFACE_THIN_SHIM = True
CANON_HTTP_BOOT_SURFACE_NO_WILDCARD_EXPORTS = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.http_boot_surface"


def build_http_boot_surface(*args, **kwargs) -> HttpBootSurface:
    return _build_http_boot_surface(*args, **kwargs)


__all__ = [
    "CANON_HTTP_BOOT_SURFACE",
    "CANON_HTTP_BOOT_SURFACE_FINAL_OWNER",
    "CANON_HTTP_BOOT_SURFACE_INTERNAL_SUPPORT",
    "CANON_HTTP_BOOT_SURFACE_NO_RUNTIME_ASSEMBLY",
    "CANON_HTTP_BOOT_SURFACE_NO_WILDCARD_EXPORTS",
    "CANON_HTTP_BOOT_SURFACE_THIN_SHIM",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "HttpBootSurface",
    "build_http_boot_surface",
]
