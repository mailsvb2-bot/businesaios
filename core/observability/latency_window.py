from __future__ import annotations

import time

CANON_LATENCY_WINDOW_HELPER = True
_MS_PER_DAY = 24 * 60 * 60 * 1000
_DEFAULT_DAYS = 1
_MAX_DAYS = 365


def _safe_days(value: object) -> int:
    try:
        days = int(value)
    except Exception:
        days = _DEFAULT_DAYS
    return max(1, min(_MAX_DAYS, days))


def _safe_now_ms(value: object | None) -> int:
    if value is None:
        return int(time.time() * 1000)
    try:
        now_ms = int(value)
    except Exception:
        return int(time.time() * 1000)
    if now_ms <= 0:
        return int(time.time() * 1000)
    return now_ms


def resolve_window_range(*, days: int, now_ms: int | None = None) -> tuple[int, int]:
    """Return a bounded latency window in epoch milliseconds."""

    safe_now = _safe_now_ms(now_ms)
    safe_days = _safe_days(days)
    start_ms = max(0, safe_now - safe_days * _MS_PER_DAY)
    return start_ms, safe_now


__all__ = ["CANON_LATENCY_WINDOW_HELPER", "resolve_window_range"]
