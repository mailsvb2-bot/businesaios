"""Thin external shim for capability-scoped runtime access."""

from __future__ import annotations

from runtime.application.contracts import RuntimeCapabilityAccess

CANON_COMPAT_SHIM = True
__all__ = ["CANON_COMPAT_SHIM", "RuntimeCapabilityAccess"]

