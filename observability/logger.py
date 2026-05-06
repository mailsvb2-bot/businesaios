from __future__ import annotations

CANON_COMPAT_SHIM = True

from observability import get_logger, log_audit, log_kv

CANON_OBSERVABILITY_LOGGER = True

__all__ = [
    "CANON_OBSERVABILITY_LOGGER",
    "get_logger",
    "log_kv",
    "log_audit",
]
