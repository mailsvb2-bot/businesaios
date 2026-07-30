"""Thin boot adapter for the canonical runtime action catalog owner."""

from __future__ import annotations

from runtime.boot_impl.actions_catalog import *  # noqa: F401,F403
from runtime.boot_impl.actions_catalog import __all__ as __all__

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_ACTION_CATALOG_ADAPTER = True
