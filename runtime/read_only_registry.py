from __future__ import annotations

"""Thin external shim for the canonical read-only runtime registry surface."""

from runtime.application.contracts import ReadOnlyRuntimeRegistry

CANON_COMPAT_SHIM = True

__all__ = ["CANON_COMPAT_SHIM", "ReadOnlyRuntimeRegistry"]
