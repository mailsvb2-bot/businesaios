from __future__ import annotations

"""Short cache window for heavy read-model computations.

This is intentionally tiny and dependency-free.
It is safe to use in read-only layers.
"""

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from config.cache_window_policy import DEFAULT_CACHE_WINDOW_POLICY, CacheWindowPolicy


@dataclass
class CacheWindow:
    window_sec: float = DEFAULT_CACHE_WINDOW_POLICY.window_sec
    policy: CacheWindowPolicy = DEFAULT_CACHE_WINDOW_POLICY

    def __post_init__(self) -> None:
        policy = self.policy or DEFAULT_CACHE_WINDOW_POLICY
        self.window_sec = float(self.window_sec if self.window_sec is not None else policy.window_sec)
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, compute: Callable[[], Any]) -> Any:
        now = time.time()
        hit = self._cache.get(str(key))
        if hit is not None:
            ts, val = hit
            if (now - float(ts)) <= float(self.window_sec):
                return val
        val = compute()
        self._cache[str(key)] = (now, val)
        return val
