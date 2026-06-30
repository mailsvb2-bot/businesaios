"""Canonical import file for the sovereign system builder.

The assembly owner remains ``bootstrap.system_builder``. This module exists so
explicit runtime entrypoints can import ``runtime.boot.system_builder`` without
depending on package-level alias side effects from ``runtime.boot.__init__``.
"""

from __future__ import annotations

from bootstrap.system_builder import build_system

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_BOOT_SYSTEM_BUILDER_COMPAT_FILE = True
CANON_SYSTEM_BUILDER_FINAL_OWNER = False
__all__ = ["build_system"]

