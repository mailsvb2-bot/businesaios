from __future__ import annotations

class CanonViolationError(RuntimeError):
    """Raised when an architectural invariant is violated."""

__all__ = [
    "CanonViolationError",
]
