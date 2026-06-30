from __future__ import annotations

from application.memory.business_memory_lock import (
    CANON_BUSINESS_MEMORY_LOCK as CANON_BUSINESS_MEMORY_LOCK,
    FileBusinessMemoryLock as FileBusinessMemoryLock,
)

CANON_BUSINESS_MEMORY_LOCK_COMPAT_SHIM = True
CANON_BUSINESS_MEMORY_LOCK_FINAL_OWNER = "application.memory.business_memory_lock"

__all__ = [
    "CANON_BUSINESS_MEMORY_LOCK",
    "CANON_BUSINESS_MEMORY_LOCK_COMPAT_SHIM",
    "CANON_BUSINESS_MEMORY_LOCK_FINAL_OWNER",
    "FileBusinessMemoryLock",
]
