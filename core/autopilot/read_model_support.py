from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from core.observability.throttled_logger import exception_throttled

logger = logging.getLogger(__name__)


def utc_now_ms(*, now_ms: Optional[int] = None) -> int:
    if now_ms is None:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    return int(now_ms)


def day_start_ms_utc(*, days_ago: int, now_ms: Optional[int] = None) -> int:
    now_dt = datetime.fromtimestamp(utc_now_ms(now_ms=now_ms) / 1000.0, tz=timezone.utc)
    d0 = datetime(now_dt.year, now_dt.month, now_dt.day, tzinfo=timezone.utc)
    d = d0 - timedelta(days=int(days_ago))
    return int(d.timestamp() * 1000)


def today_start_ms(*, now_ms: Optional[int] = None) -> int:
    return day_start_ms_utc(days_ago=0, now_ms=now_ms)


def collect_unique_users(*, event_store: Any, tenant_id: str, start_ms: int, end_ms: Optional[int], event_type: str) -> Set[str]:
    users: Set[str] = set()
    tenant_value = str(tenant_id)
    start_value = int(start_ms)
    event_type_value = str(event_type)
    end_value = int(end_ms) if end_ms is not None else None
    if end_value is None:
        events = event_store.iter_events(tenant_id=tenant_value, start_ms=start_value, event_type=event_type_value)
    else:
        events = event_store.iter_events(tenant_id=tenant_value, start_ms=start_value, end_ms=end_value, event_type=event_type_value)
    for ev in events:
        uid = ev.get("user_id")
        if uid and uid != "system":
            users.add(str(uid))
    return users


def collect_revenue_and_users(*, event_store: Any, tenant_id: str, start_ms: int, end_ms: Optional[int], event_type: str, amount_key: str) -> Tuple[Set[str], int]:
    users = collect_unique_users(
        event_store=event_store,
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=end_ms,
        event_type=event_type,
    )
    revenue_minor = 0
    tenant_value = str(tenant_id)
    start_value = int(start_ms)
    event_type_value = str(event_type)
    end_value = int(end_ms) if end_ms is not None else None
    if end_value is None:
        events = event_store.iter_events(tenant_id=tenant_value, start_ms=start_value, event_type=event_type_value)
    else:
        events = event_store.iter_events(tenant_id=tenant_value, start_ms=start_value, end_ms=end_value, event_type=event_type_value)
    for ev in events:
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        try:
            revenue_minor += int(payload.get(amount_key) or 0)
        except Exception:
            exception_throttled(logger, key=f"read_model.{event_type}.{amount_key}", msg="read_model: failed to parse revenue payload")
    return users, revenue_minor


def collect_ads_metrics(*, event_store: Any, tenant_id: str, start_ms: int, end_ms: int) -> Dict[str, int]:
    spend_minor = 0
    conversions = 0
    for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms), event_type="ads_metrics_imported"):
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
        try:
            spend_minor += int(round(float(metrics.get("spend") or 0.0) * 100))
        except Exception:
            exception_throttled(logger, key="read_model.ads_spend_minor", msg="read_model: failed to parse ads spend")
        try:
            conversions += int(metrics.get("conversions") or 0)
        except Exception:
            exception_throttled(logger, key="read_model.ads_conversions", msg="read_model: failed to parse ads conversions")
    return {"spend_minor": int(spend_minor), "conversions": int(conversions)}


def collect_recent_autopilot_action_rows(*, event_store: Any, tenant_id: str, start_ms: int, end_ms: int) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []
    for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms), event_type="autopilot_decision@v1"):
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        out.append(
            {
                "ts_ms": int(ev.get("timestamp_ms") or 0),
                "user_id": str(ev.get("user_id") or ""),
                "kind": str(payload.get("kind") or ""),
                "reason": str(payload.get("reason") or ""),
                "changes": payload.get("changes") if isinstance(payload.get("changes"), dict) else {},
            }
        )
    out.sort(key=lambda x: int(x.get("ts_ms") or 0), reverse=True)
    return out[:50]


__all__ = [
    "collect_ads_metrics",
    "collect_recent_autopilot_action_rows",
    "collect_revenue_and_users",
    "collect_unique_users",
    "day_start_ms_utc",
    "today_start_ms",
    "utc_now_ms",
]
