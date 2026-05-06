from __future__ import annotations

from typing import Any, Dict, List, Set

from core.admin.read_models.traffic_support import (
    iter_events_window,
    resolve_now_ms,
    safe_count_distinct_users_window,
    safe_count_events_window,
    start_of_utc_day_ms,
    window_start_ms,
)


def users_today(event_store: Any, *, tenant_id: str = "default", now_ms: int | None = None) -> int:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return 0
    now_ms_resolved = resolve_now_ms(now_ms=now_ms)
    start_ms = start_of_utc_day_ms(now_ms=now_ms_resolved)
    count = safe_count_distinct_users_window(
        event_store,
        tenant_id=str(tenant_id),
        start_ms=start_ms,
        end_ms=now_ms_resolved,
        event_type=None,
    )
    if count:
        return int(count)
    seen: Set[str] = set()
    for ev in iter_events_window(event_store, tenant_id=str(tenant_id), start_ms=start_ms, end_ms=now_ms_resolved):
        uid = ev.get("user_id")
        if uid and uid != "system":
            seen.add(str(uid))
    return int(len(seen))


def funnel_counts(
    event_store: Any,
    event_types: List[str],
    *,
    tenant_id: str = "default",
    start_ms: int = 0,
    end_ms: int | None = None,
) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for et in event_types:
        if not et:
            continue
        if end_ms is not None:
            counted = safe_count_distinct_users_window(
                event_store,
                tenant_id=str(tenant_id),
                start_ms=int(start_ms),
                end_ms=int(end_ms),
                event_type=str(et),
            )
            if counted:
                out[et] = int(counted)
                continue
        seen: Set[str] = set()
        iterator = (
            iter_events_window(event_store, tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms), event_type=str(et))
            if end_ms is not None
            else event_store.iter_events(tenant_id=str(tenant_id), start_ms=int(start_ms), event_type=str(et))
        )
        for ev in iterator:
            uid = ev.get("user_id")
            if uid and uid != "system":
                seen.add(str(uid))
        out[et] = int(len(seen))
    return out


def demo_summary(event_store: Any, *, tenant_id: str = "default", days: int = 30, now_ms: int | None = None) -> Dict[str, Any]:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"sent_work": 0, "sent_home": 0, "users": 0}
    now_ms_resolved = resolve_now_ms(now_ms=now_ms)
    start_ms = window_start_ms(now_ms=now_ms_resolved, days=days)
    users = safe_count_distinct_users_window(
        event_store,
        tenant_id=str(tenant_id),
        start_ms=start_ms,
        end_ms=now_ms_resolved,
        event_type="audio_sent",
    )
    sent_work = sent_home = 0
    seen_users: Set[str] = set()
    for ev in iter_events_window(event_store, tenant_id=str(tenant_id), start_ms=start_ms, end_ms=now_ms_resolved, event_type="audio_sent"):
        uid = ev.get("user_id")
        if not uid or uid == "system":
            continue
        seen_users.add(str(uid))
        path = str((ev.get("payload") or {}).get("path") or "")
        if "work" in path:
            sent_work += 1
        elif "home" in path:
            sent_home += 1
    return {"sent_work": int(sent_work), "sent_home": int(sent_home), "users": int(users or len(seen_users))}


def segments_summary(event_store: Any, *, tenant_id: str = "default", days: int = 30, now_ms: int | None = None) -> Dict[str, int]:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"new_users": 0, "active_users_7d": 0, "payers_30d": 0, "granted_30d": 0}

    now_ms_resolved = resolve_now_ms(now_ms=now_ms)
    start_today_ms = start_of_utc_day_ms(now_ms=now_ms_resolved)
    start_7d_ms = window_start_ms(now_ms=now_ms_resolved, days=7)
    start_30d_ms = window_start_ms(now_ms=now_ms_resolved, days=30)

    return {
        "new_users": safe_count_distinct_users_window(event_store, tenant_id=str(tenant_id), start_ms=start_today_ms, end_ms=now_ms_resolved),
        "active_users_7d": safe_count_distinct_users_window(event_store, tenant_id=str(tenant_id), start_ms=start_7d_ms, end_ms=now_ms_resolved),
        "payers_30d": safe_count_distinct_users_window(event_store, tenant_id=str(tenant_id), start_ms=start_30d_ms, end_ms=now_ms_resolved, event_type="payment_captured"),
        "granted_30d": safe_count_distinct_users_window(event_store, tenant_id=str(tenant_id), start_ms=start_30d_ms, end_ms=now_ms_resolved, event_type="access_granted"),
    }


def funnel2_report(event_store: Any, *, tenant_id: str = "default", days: int = 7, now_ms: int | None = None) -> Dict[str, Any]:
    now_ms_resolved = resolve_now_ms(now_ms=now_ms)
    start_ms = window_start_ms(now_ms=now_ms_resolved, days=days)
    stages = [
        ("tariffs_viewed", "Tariffs viewed"),
        ("tariff_selected", "Tariff selected"),
        ("payment_created", "Payment created"),
        ("payment_captured", "Payment captured"),
        ("access_granted", "Access granted"),
        ("audio_sent", "First audio sent"),
    ]
    counts = funnel_counts(event_store, [s[0] for s in stages], tenant_id=tenant_id, start_ms=start_ms, end_ms=now_ms_resolved)
    base = max(1, counts.get("tariffs_viewed", 0))
    rates = {k: round((counts.get(k, 0) / base) * 100.0, 2) for k, _ in stages}
    return {"start_ms": start_ms, "days": int(days), "counts": counts, "rates_pct_from_view": rates, "stages": stages}


def ab_offers_summary(event_store: Any, *, tenant_id: str = "default", days: int = 30, now_ms: int | None = None) -> Dict[str, Any]:
    now_ms_resolved = resolve_now_ms(now_ms=now_ms)
    start_ms = window_start_ms(now_ms=now_ms_resolved, days=days)
    variants = safe_count_events_window(event_store, tenant_id=str(tenant_id), event_type="marketing_copy_set", start_ms=start_ms, end_ms=now_ms_resolved)
    chosen = safe_count_events_window(event_store, tenant_id=str(tenant_id), event_type="marketing_copy_chosen", start_ms=start_ms, end_ms=now_ms_resolved)
    if variants or chosen:
        return {"variants_set": int(variants), "variants_chosen": int(chosen)}
    return {"variants_set": 0, "variants_chosen": 0}


def giftshare_summary(event_store: Any, *, tenant_id: str = "default", days: int = 30, now_ms: int | None = None) -> Dict[str, int]:
    now_ms_resolved = resolve_now_ms(now_ms=now_ms)
    start_ms = window_start_ms(now_ms=now_ms_resolved, days=days)
    shares = safe_count_events_window(event_store, tenant_id=str(tenant_id), event_type="share_clicked", start_ms=start_ms, end_ms=now_ms_resolved)
    gifts = safe_count_events_window(event_store, tenant_id=str(tenant_id), event_type="gift_sent", start_ms=start_ms, end_ms=now_ms_resolved)
    if shares or gifts:
        return {"share_clicked": int(shares), "gift_sent": int(gifts)}
    return {"share_clicked": 0, "gift_sent": 0}
