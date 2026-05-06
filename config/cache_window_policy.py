from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class CacheWindowPolicy:
    window_sec: float = 5.0


DEFAULT_CACHE_WINDOW_POLICY = CacheWindowPolicy()
