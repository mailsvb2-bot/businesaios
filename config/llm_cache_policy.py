from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LLMCachePolicy:
    ttl_s: float = 600.0
    max_items: int = 2048
