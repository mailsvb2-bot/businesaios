from __future__ import annotations

"""Compatibility shell for the canonical runtime boot manifest owner.

The canonical owner is ``bootstrap.runtime_boot_manifest``. This module exists
only so legacy ``boot.*`` imports resolve to the same owner instead of breaking
sovereign boot after cleanup/collapse waves. It must not build services and must
not define an independent manifest catalog.
"""

CANON_BOOT_RUNTIME_BOOT_MANIFEST_COMPAT_SHELL = True
CANON_BOOT_RUNTIME_BOOT_MANIFEST_NO_RUNTIME_ASSEMBLY = True

from bootstrap.runtime_boot_manifest import (  # noqa: F401
    CANON_RUNTIME_BOOT_MANIFEST_FINAL_OWNER,
    RUNTIME_BOOT_MANIFEST,
)

__all__ = [
    "CANON_BOOT_RUNTIME_BOOT_MANIFEST_COMPAT_SHELL",
    "CANON_BOOT_RUNTIME_BOOT_MANIFEST_NO_RUNTIME_ASSEMBLY",
    "CANON_RUNTIME_BOOT_MANIFEST_FINAL_OWNER",
    "RUNTIME_BOOT_MANIFEST",
]
