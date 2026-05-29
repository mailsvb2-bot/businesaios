from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Optional

from config.llm_cache_policy import LLMCachePolicy


@dataclass
class CacheEntry:
    value: str
    expires_at: float


class TTLTextCache:
    def __init__(
        self,
        *,
        ttl_s: float | None = None,
        max_items: int | None = None,
        policy: LLMCachePolicy | None = None,
    ) -> None:
        resolved_policy = policy or LLMCachePolicy()
        self.policy = resolved_policy
        self.ttl_s = float(resolved_policy.ttl_s if ttl_s is None else ttl_s)
        self.max_items = int(resolved_policy.max_items if max_items is None else max_items)
        self._store: dict[str, CacheEntry] = {}

    def _now(self) -> float:
        return time.time()

    def _prune(self) -> None:
        now = self._now()
        for k in list(self._store.keys()):
            if self._store[k].expires_at <= now:
                del self._store[k]
        if len(self._store) > self.max_items:
            for k in list(self._store.keys())[: len(self._store) - self.max_items]:
                del self._store[k]

    def make_key(self, s: str) -> str:
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        self._prune()
        e = self._store.get(key)
        if not e:
            return None
        if e.expires_at <= self._now():
            self._store.pop(key, None)
            return None
        return e.value

    def set(self, key: str, value: str) -> None:
        self._prune()
        self._store[key] = CacheEntry(value=value, expires_at=self._now() + self.ttl_s)
