from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMCachePolicy:
    ttl_s: float = 600.0
    max_items: int = 2048
