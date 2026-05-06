from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Thin compatibility wrapper for legacy imports.

The canonical implementations live in ``runtime.boot.actions_catalog`` so there
is only one place that owns action-row registry assembly semantics.
"""

from runtime.boot.actions_catalog import build_inline_allowlist, build_specs_registry

__all__ = ["build_inline_allowlist", "build_specs_registry"]
