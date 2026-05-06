from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class DedupeConfig:
    cooldown_s: float = 6 * 3600
    max_items: int = 4096


class MessageDedupe:
    """In-memory dedupe based on (tenant,user,text_hash)."""

    def __init__(self, cfg: DedupeConfig) -> None:
        self._cfg = cfg
        self._seen: Dict[Tuple[str, str, str], float] = {}

    def _now(self) -> float:
        return time.time()

    def _prune(self) -> None:
        now = self._now()
        for k, ts in list(self._seen.items()):
            if ts <= now:
                del self._seen[k]
        if len(self._seen) > int(self._cfg.max_items):
            for k in list(self._seen.keys())[: len(self._seen) - int(self._cfg.max_items)]:
                del self._seen[k]

    def _h(self, text: str) -> str:
        return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()

    def allow(self, *, tenant_id: str, user_id: str, text: str) -> bool:
        self._prune()
        key = (str(tenant_id), str(user_id), self._h(text))
        now = self._now()
        if key in self._seen and self._seen[key] > now:
            return False
        self._seen[key] = now + float(self._cfg.cooldown_s)
        return True
