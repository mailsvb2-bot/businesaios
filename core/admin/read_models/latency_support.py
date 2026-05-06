from __future__ import annotations

from typing import Tuple

from core.admin.read_models.common_support import resolve_now_ms


def resolve_window_range(*, days: int, now_ms: int | None) -> Tuple[int, int]:
    resolved_now_ms = resolve_now_ms(now_ms=now_ms)
    start_ms = resolved_now_ms - int(days) * 24 * 3600 * 1000
    return int(start_ms), int(resolved_now_ms)
