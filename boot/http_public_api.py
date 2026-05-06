from __future__ import annotations
"""Transition bridge for HTTP boot.
This module intentionally stays tiny. It must not become a second public owner
because the sovereign bootstrap path lives at ``bootstrap.http_boot_surface``.
"""

from typing import Any

CANON_HTTP_BOOT_PUBLIC_API = True
CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_HTTP_PUBLIC_API_DIRECT_SURFACE_DELEGATION = True
CANON_HTTP_PUBLIC_API_DIRECT_BOOTSTRAP_SURFACE = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.http_boot_surface"

__all__ = [
    "CANON_HTTP_BOOT_PUBLIC_API",
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANON_HTTP_PUBLIC_API_DIRECT_SURFACE_DELEGATION",
    "CANON_HTTP_PUBLIC_API_DIRECT_BOOTSTRAP_SURFACE",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "boot_http_app",
]


def boot_http_app(*args: Any, **kwargs: Any):
    from bootstrap.http_boot_surface import build_http_boot_surface as _build_http_boot_surface

    return _build_http_boot_surface(*args, **kwargs).http_app
