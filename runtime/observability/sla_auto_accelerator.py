"""SLA auto-accelerator.

If latency increases, we temporarily extend the read-model cache window.
This is best-effort and reversible. Truth remains in events.

Important: this module must not mutate os.environ directly except through
runtime.read_models.cache_window, to avoid "God code" leaks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from runtime.platform.config.env_flags import env_int
from runtime.read_models.cache_window import set_cache_window_seconds


@dataclass(frozen=True)
class SlaAcceleratorConfig:
    interval_s: int = 30
    base_ttl_ms: int = 2000
    max_ttl_ms: int = 15000

    @staticmethod
    def from_env() -> SlaAcceleratorConfig:
        interval_s = max(5, min(600, env_int("SLA_ACCELERATOR_INTERVAL_S", 30)))
        base_ttl_ms = max(100, min(60_000, env_int("SLA_ACCELERATOR_BASE_TTL_MS", 2000)))
        max_ttl_ms = max(base_ttl_ms, min(120_000, env_int("SLA_ACCELERATOR_MAX_TTL_MS", 15000)))
        return SlaAcceleratorConfig(interval_s=interval_s, base_ttl_ms=base_ttl_ms, max_ttl_ms=max_ttl_ms)


_LAST_ADJUST_MS: int | None = None
_LAST_TTL_MS: int | None = None


def maybe_adjust_read_model_cache_window(*, event_log: Any = None) -> None:
    """Best-effort adaptive tuning for read-model cache window.

    Uses runtime perf surface rolling latency summary to select a cache TTL.
    This does NOT replace truth; it only helps smooth transient latency spikes.
    """

    global _LAST_ADJUST_MS, _LAST_TTL_MS
    try:
        now_ms = int(time.time() * 1000)
        cfg = SlaAcceleratorConfig.from_env()
        interval_s = int(cfg.interval_s)
        if _LAST_ADJUST_MS is not None and (now_ms - int(_LAST_ADJUST_MS)) < interval_s * 1000:
            return
        _LAST_ADJUST_MS = now_ms

        from runtime.observability.perf import AutoAccelerator, rolling_latency_summary

        summary = rolling_latency_summary(top_n=3)
        accel = AutoAccelerator(base_ttl_ms=int(cfg.base_ttl_ms), max_ttl_ms=int(cfg.max_ttl_ms))
        ttl_ms = int(accel.recommend_ttl_ms(latency_summary=summary))

        if _LAST_TTL_MS is not None and int(_LAST_TTL_MS) == ttl_ms:
            return
        _LAST_TTL_MS = ttl_ms

        set_cache_window_seconds(float(ttl_ms) / 1000.0)

        if event_log is not None and hasattr(event_log, "emit"):
            event_log.emit(
                {
                    "event_type": "sla_auto_accelerator_adjusted",
                    "source": "runtime.observability",
                    "user_id": "system",
                    "timestamp_ms": now_ms,
                    "payload": {"ttl_ms": ttl_ms, "summary": summary},
                }
            )
    except Exception:
        return
