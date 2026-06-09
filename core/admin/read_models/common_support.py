from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from collections.abc import Iterable

from core.tenancy.normalization import normalize_tenant_scope
from core.utils.call_signature import accepts_keyword


def resolve_now_ms(*, now_ms: int | None) -> int:
    if now_ms is not None:
        return int(now_ms)
    return int(datetime.now(UTC).timestamp() * 1000)


def supports_kwarg(fn: Any, kw: str) -> bool:
    return accepts_keyword(fn, kw)




def normalize_admin_tenant_id(tenant_id: Any) -> str:
    return normalize_tenant_scope(tenant_id, allow_unknown=True)


def iter_events_bounded(
    event_store: Any,
    *,
    tenant_id: str,
    start_ms: int | None = None,
    end_ms: int | None = None,
    event_type: str | None = None,
) -> Iterable[dict[str, Any]]:
    tenant_id_value = str(tenant_id)
    start_ms_value = int(start_ms) if start_ms is not None else 0
    end_ms_value = int(end_ms) if end_ms is not None else None
    event_type_value = str(event_type) if event_type is not None else None

    supports_end_ms = end_ms_value is not None and supports_kwarg(event_store.iter_events, "end_ms")

    if supports_end_ms:
        return event_store.iter_events(tenant_id=tenant_id_value,
            start_ms=start_ms_value,
            end_ms=end_ms_value,
            event_type=event_type_value,
        )

    def _fallback_iter() -> Iterable[dict[str, Any]]:
        for ev in event_store.iter_events(tenant_id=tenant_id_value,
            start_ms=start_ms_value,
            event_type=event_type_value,
        ):
            try:
                ts = int(ev.get("timestamp_ms") or 0)
            except Exception:
                continue
            if end_ms_value is not None and ts > end_ms_value:
                continue
            yield ev

    return _fallback_iter()


def count_distinct_users_window(
    event_store: Any,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    event_type: str | None = None,
) -> int:
    if hasattr(event_store, "count_distinct_users") and supports_kwarg(event_store.count_distinct_users, "end_ms"):
        return int(
            event_store.count_distinct_users(
                tenant_id=str(tenant_id),
                start_ms=int(start_ms),
                end_ms=int(end_ms),
                event_type=event_type,
            )
        )
    seen: set[str] = set()
    for ev in iter_events_bounded(
        event_store,
        tenant_id=str(tenant_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        event_type=event_type,
    ):
        uid = ev.get("user_id")
        if uid and uid != "system":
            seen.add(str(uid))
    return int(len(seen))


def count_events_window(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int,
    end_ms: int,
) -> int:
    if hasattr(event_store, "count_events") and supports_kwarg(event_store.count_events, "end_ms"):
        return int(
            event_store.count_events(tenant_id=str(tenant_id),
                event_type=str(event_type),
                start_ms=int(start_ms),
                end_ms=int(end_ms),
            )
        )
    count = 0
    for _ in iter_events_bounded(
        event_store,
        tenant_id=str(tenant_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        event_type=str(event_type),
    ):
        count += 1
    return int(count)


__all__ = [
    "count_distinct_users_window",
    "count_events_window",
    "iter_events_bounded",
    "normalize_admin_tenant_id",
    "resolve_now_ms",
    "supports_kwarg",
]
