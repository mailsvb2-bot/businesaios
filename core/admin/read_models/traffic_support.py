from __future__ import annotations

from datetime import datetime, timezone, UTC
from typing import Any, Iterable

from core.admin.read_models.common_support import (
    count_distinct_users_window,
    count_events_window,
    iter_events_bounded,
    resolve_now_ms,
    supports_kwarg,
)
from core.observability.silent import swallow


def start_of_utc_day_ms(*, now_ms: int) -> int:
    now = datetime.fromtimestamp(int(now_ms) / 1000.0, tz=UTC)
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return int(start.timestamp() * 1000)


def window_start_ms(*, now_ms: int, days: int) -> int:
    return max(0, int(now_ms) - int(days) * 24 * 3600 * 1000)


def iter_events_window(
    event_store: Any,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    event_type: str | None = None,
) -> Iterable[dict[str, Any]]:
    return iter_events_bounded(
        event_store,
        tenant_id=str(tenant_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        event_type=event_type,
    )


def safe_count_distinct_users_window(
    event_store: Any,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    event_type: str | None = None,
) -> int:
    try:
        return count_distinct_users_window(
            event_store,
            tenant_id=str(tenant_id),
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            event_type=event_type,
        )
    except Exception:
        swallow(__name__, "core/admin/read_model.py")
        return 0


def safe_count_events_window(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int,
    end_ms: int,
) -> int:
    try:
        return count_events_window(
            event_store,
            tenant_id=str(tenant_id),
            event_type=str(event_type),
            start_ms=int(start_ms),
            end_ms=int(end_ms),
        )
    except Exception:
        swallow(__name__, "core/admin/read_model.py")
        return 0


__all__ = [
    "iter_events_window",
    "resolve_now_ms",
    "safe_count_distinct_users_window",
    "safe_count_events_window",
    "start_of_utc_day_ms",
    "supports_kwarg",
    "window_start_ms",
]
