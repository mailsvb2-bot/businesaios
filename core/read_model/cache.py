from __future__ import annotations

"""Read-model accelerator: TTL cache + event watermark invalidation."""

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Optional, Tuple, TypeVar

from config.env_flags import env_float
from config.read_model_cache_policy import (
    DEFAULT_READ_MODEL_CACHE_POLICY,
    ReadModelCachePolicy,
)
from core.events.read_model_support import best_effort_latest_event

T = TypeVar("T")


def cache_window_s(*, policy: ReadModelCachePolicy = DEFAULT_READ_MODEL_CACHE_POLICY) -> float:
    return max(
        float(policy.min_window_s),
        min(float(policy.max_window_s), float(env_float("READ_MODEL_CACHE_WINDOW_S", float(policy.default_window_s)))),
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class _Entry:
    value: Any
    computed_at_ms: int
    watermark_ms: int


class ReadModelCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[Hashable, _Entry] = {}

    def get(
        self,
        *,
        key: Hashable,
        compute: Callable[[], T],
        watermark_ms: int,
        window_s: float | None = None,
    ) -> T:
        win = cache_window_s() if window_s is None else float(window_s)
        if win <= 0:
            return compute()

        now_ms = _now_ms()
        with self._lock:
            e = self._data.get(key)
            if e is not None:
                if int(e.watermark_ms) == int(watermark_ms) and (now_ms - int(e.computed_at_ms)) <= int(win * 1000):
                    return e.value  # type: ignore[return-value]

        val = compute()
        with self._lock:
            self._data[key] = _Entry(value=val, computed_at_ms=now_ms, watermark_ms=int(watermark_ms))
        return val

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_CACHE = ReadModelCache()


def global_cache() -> ReadModelCache:
    return _CACHE


def watermark_for(
    event_store: Any,
    *,
    tenant_id: str = "default",
    user_id: str | None = None,
    event_types: tuple[str, ...] | None = None,
) -> int:
    """Best-effort watermark: latest event timestamp for a user (optionally filtered)."""
    if event_store is None:
        return int(DEFAULT_READ_MODEL_CACHE_POLICY.default_empty_watermark_ms)
    ev = best_effort_latest_event(
        event_store=event_store,
        where='core/read_model/cache.watermark_for',
        tenant_id=str(tenant_id),
        user_id=(str(user_id) if user_id is not None else None),
        event_types=tuple(event_types or ()),
        legacy_event_type=(event_types[0] if event_types else None),
    )
    if isinstance(ev, dict) and ev.get("timestamp_ms") is not None:
        return int(ev.get("timestamp_ms") or 0)
    return int(DEFAULT_READ_MODEL_CACHE_POLICY.default_empty_watermark_ms)
