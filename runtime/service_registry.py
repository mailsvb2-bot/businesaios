"""Thin external shim for canonical service registry types.

No wildcard exports and no root-level registry ownership are allowed here.
"""

from __future__ import annotations

from shared.registry import Registry, ServiceRegistry

CANON_COMPAT_SHIM = True
CANON_NO_WILDCARD_EXPORT = True

__all__ = ["CANON_COMPAT_SHIM", "CANON_NO_WILDCARD_EXPORT", "Registry", "ServiceRegistry"]
