from __future__ import annotations

from application.memory.business_memory_query import (
    BusinessMemoryQueryService as BusinessMemoryQueryService,
    CANON_BUSINESS_MEMORY_QUERY as CANON_BUSINESS_MEMORY_QUERY,
)

CANON_BUSINESS_MEMORY_QUERY_COMPAT_SHIM = True
CANON_BUSINESS_MEMORY_QUERY_FINAL_OWNER = "application.memory.business_memory_query"

__all__ = [
    "BusinessMemoryQueryService",
    "CANON_BUSINESS_MEMORY_QUERY",
    "CANON_BUSINESS_MEMORY_QUERY_COMPAT_SHIM",
    "CANON_BUSINESS_MEMORY_QUERY_FINAL_OWNER",
]
