from __future__ import annotations

from application.memory.business_memory_matcher import (
    BusinessMemoryMatcher as BusinessMemoryMatcher,
    CANON_BUSINESS_MEMORY_MATCHER as CANON_BUSINESS_MEMORY_MATCHER,
    MemoryRunFingerprint as MemoryRunFingerprint,
    SimilarRunMatch as SimilarRunMatch,
)

CANON_BUSINESS_MEMORY_MATCHER_COMPAT_SHIM = True
CANON_BUSINESS_MEMORY_MATCHER_FINAL_OWNER = "application.memory.business_memory_matcher"

__all__ = [
    "BusinessMemoryMatcher",
    "CANON_BUSINESS_MEMORY_MATCHER",
    "CANON_BUSINESS_MEMORY_MATCHER_COMPAT_SHIM",
    "CANON_BUSINESS_MEMORY_MATCHER_FINAL_OWNER",
    "MemoryRunFingerprint",
    "SimilarRunMatch",
]
