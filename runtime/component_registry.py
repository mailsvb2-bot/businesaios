from __future__ import annotations

"""Thin external shim for canonical component registry types.

No wildcard exports and no root-level registry ownership are allowed here.
"""

from shared.registry import ComponentRegistry, Registry

CANON_COMPAT_SHIM = True
CANON_NO_WILDCARD_EXPORT = True

__all__ = ["CANON_COMPAT_SHIM", "CANON_NO_WILDCARD_EXPORT", "ComponentRegistry", "Registry"]
