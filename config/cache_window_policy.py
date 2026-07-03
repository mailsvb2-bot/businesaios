from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class CacheWindowPolicy:
    window_sec: float = 5.0


DEFAULT_CACHE_WINDOW_POLICY = CacheWindowPolicy()
