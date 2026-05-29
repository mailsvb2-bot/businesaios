from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Any, Dict, Set

from core.admin.read_models.retention_support import iter_events_window, resolve_now_ms


def retention_brief(event_store: Any, *, tenant_id: str = "default", days: int = 30, now_ms: int | None = None) -> dict[str, int]:
    """Very simple retention proxy: users who had >=2 active days in the last N days.

    Performance: uses DB-side aggregation when available.
    """
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"users": 0, "active_2d": 0}

    now_ms = resolve_now_ms(now_ms=now_ms)
    start_ms = max(0, now_ms - int(days) * 24 * 3600 * 1000)

    per_user_days: dict[str, set[str]] = {}
    for ev in iter_events_window(event_store, tenant_id=str(tenant_id), start_ms=start_ms, end_ms=now_ms):
        uid = ev.get("user_id")
        if not uid or uid == "system":
            continue
        ts = int(ev.get("timestamp_ms") or 0)
        day = datetime.fromtimestamp(ts / 1000, tz=UTC).strftime("%Y-%m-%d")
        per_user_days.setdefault(str(uid), set()).add(day)
    users = len(per_user_days)
    active_2d = sum(1 for _, ds in per_user_days.items() if len(ds) >= 2)
    return {"users": int(users), "active_2d": int(active_2d)}


def health_brief(event_store: Any, *, tenant_id: str = "default", now_ms: int | None = None) -> dict[str, int]:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"events": 0}
    n = 0
    end_ms = resolve_now_ms(now_ms=now_ms)
    for _ in iter_events_window(event_store, tenant_id=str(tenant_id), start_ms=0, end_ms=end_ms):
        n += 1
    return {"events": int(n)}
