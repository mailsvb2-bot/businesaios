from __future__ import annotations

"""Canonical runtime exception-observability surface.

Runtime best-effort paths should depend on this adapter instead of reaching into
core observability internals directly.
"""

from core.observability.silent import swallow
from core.observability.throttled_logger import exception_throttled, warning_throttled

CANON_RUNTIME_ERROR_OBSERVABILITY_PUBLIC_API = True

__all__ = [
    "CANON_RUNTIME_ERROR_OBSERVABILITY_PUBLIC_API",
    "exception_throttled",
    "swallow",
    "warning_throttled",
]
