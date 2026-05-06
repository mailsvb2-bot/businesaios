from __future__ import annotations

"""Thin external shim for capability-scoped runtime access."""

from runtime.application.contracts import RuntimeCapabilityAccess

CANON_COMPAT_SHIM = True

__all__ = ["CANON_COMPAT_SHIM", "RuntimeCapabilityAccess"]
