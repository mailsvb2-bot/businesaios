from __future__ import annotations

"""Thin external shim for typed runtime access."""

from runtime.application.contracts import RuntimeTypedAccess

CANON_COMPAT_SHIM = True

__all__ = ["CANON_COMPAT_SHIM", "RuntimeTypedAccess"]
