from __future__ import annotations

from core.admin.read_models.common_support import resolve_now_ms


def resolve_window_bounds(*, now_ms: int | None, window_days: int) -> tuple[int, int]:
    resolved_now_ms = resolve_now_ms(now_ms=now_ms)
    start_ms = resolved_now_ms - int(max(1, int(window_days))) * 24 * 3600 * 1000
    return int(start_ms), int(resolved_now_ms)
