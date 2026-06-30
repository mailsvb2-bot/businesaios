"""Compatibility package surface. Final owner: application.world_state."""

from __future__ import annotations

from importlib import import_module

CANON_COMPAT_SHIM = True
CANONICAL_OWNER_MODULE = "application.world_state"
__all__ = ["assemble_world_state"]

def __getattr__(name: str):
    if name == "assemble_world_state":
        return getattr(import_module("application.world_state"), name)
    raise AttributeError(name)
