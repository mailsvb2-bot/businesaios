from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from typing import Any

from config.strategic_growth_policy import DEFAULT_GROWTH_SIGNALS_POLICY, GrowthSignalsPolicy
from core.actions.names import ACTION_ADS_APPLY_EXECUTE_V1
from core.growth.today_ledger import build_today_kpi
from core.observability.errors import log_exception_throttled

from .contracts import GrowthSignalV1
from .sales_funnel import empty_sales_funnel, read_sales_funnel

log = logging.getLogger(__name__)


def _compute_retention(
    events: Iterable[dict[str, Any]],
    *,
    window_days: int | None = None,
    return_days: int | None = None,
    policy: GrowthSignalsPolicy = DEFAULT_GROWTH_SIGNALS_POLICY,
) -> float:
    """Simple retention ratio: returning / active within a window."""
    now_ms = int(time.time() * 1000)
    active_window_days = policy.retention_window_days if window_days is None else int(window_days)
    recent_window_days = policy.retention_d7_days if return_days is None else int(return_days)
    window_ms = active_window_days * 24 * 3600 * 1000
    return_ms = recent_window_days * 24 * 3600 * 1000
    active = set()
    recent = set()
    for event in events:
        try:
            uid = str(event.get("user_id") or "")
            ts = int(event.get("timestamp_ms") or 0)
        except Exception:
            continue
        if not uid:
            continue
        if now_ms - ts <= window_ms:
            active.add(uid)
        if now_ms - ts <= return_ms:
            recent.add(uid)
    if not active:
        return policy.zero_ratio
    return float(len(active & recent)) / float(len(active))


def _sales_funnel(
    event_store: Any,
    *,
    tenant_id: str,
    now_ms: int,
    policy: GrowthSignalsPolicy,
) -> dict[str, Any]:
    start_ms = now_ms - max(1, int(policy.sales_funnel_window_days)) * int(policy.day_ms)
    if not callable(getattr(event_store, "iter_events", None)):
        return empty_sales_funnel(tenant_id=tenant_id, start_ms=start_ms, end_ms=now_ms)
    try:
        return read_sales_funnel(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=now_ms)
    except Exception as exc:
        log_exception_throttled(log, "growth_sales_funnel_projection_failed", exc)
        return empty_sales_funnel(tenant_id=tenant_id, start_ms=start_ms, end_ms=now_ms)


def build_signals(
    event_store: Any,
    *,
    tenant_id: str,
    limit: int | None = None,
    policy: GrowthSignalsPolicy = DEFAULT_GROWTH_SIGNALS_POLICY,
) -> GrowthSignalV1:
    now_ms = int(time.time() * 1000)
    kpi = build_today_kpi(event_store, tenant_id=tenant_id)
    scan_limit = policy.event_scan_limit if limit is None else int(limit)
    events = list(_latest_any_events(event_store, tenant_id=tenant_id, limit=scan_limit, policy=policy))
    d1 = _compute_retention(events, window_days=policy.retention_window_days, return_days=policy.retention_d1_days, policy=policy) * policy.percentage_multiplier
    d7 = _compute_retention(events, window_days=policy.retention_window_days, return_days=policy.retention_d7_days, policy=policy) * policy.percentage_multiplier
    leads = int(kpi.leads)
    purchases = _count_events_today(events, event_type="purchase_completed@v1")
    conv = (float(purchases) / float(leads) * policy.percentage_multiplier) if leads > 0 else policy.zero_ratio
    return GrowthSignalV1(
        ts_ms=now_ms,
        tenant_id=str(tenant_id),
        leads_today=leads,
        spend_today_minor=int(kpi.spend_minor),
        revenue_today_minor=int(kpi.revenue_minor),
        profit_today_minor=int(kpi.profit_minor),
        retention_d1_pct=float(round(d1, 2)),
        retention_d7_pct=float(round(d7, 2)),
        conversion_lead_to_purchase_pct=float(round(conv, 2)),
        top_channels=tuple(_top_channels(events, top_n=policy.top_channels_limit)),
        notes=tuple(_notes(events)),
        sales_funnel=_sales_funnel(event_store, tenant_id=str(tenant_id), now_ms=now_ms, policy=policy),
    )


def _latest_any_events(
    event_store: Any,
    *,
    tenant_id: str,
    limit: int,
    policy: GrowthSignalsPolicy = DEFAULT_GROWTH_SIGNALS_POLICY,
) -> Iterable[dict[str, Any]]:
    latest = getattr(event_store, "latest_events", None)
    if callable(latest):
        try:
            res = latest(tenant_id=tenant_id, event_types=None, limit=int(limit))
            if res:
                yield from res
                return
        except Exception as exc:
            log_exception_throttled(log, "growth_signals_latest_events_failed", exc)
    for event_type in policy.common_event_types:
        yield from _latest_events(
            event_store,
            tenant_id=tenant_id,
            event_type=event_type,
            limit=max(policy.fallback_event_limit_floor, int(limit // policy.fallback_event_limit_divisor)),
        )


def _latest_events(event_store: Any, *, tenant_id: str, event_type: str, limit: int) -> Iterable[dict[str, Any]]:
    latest = getattr(event_store, "latest_events", None)
    if callable(latest):
        try:
            yield from latest(tenant_id=tenant_id, event_types=(event_type,), limit=int(limit)) or []
        except Exception:
            return


def _count_events_today(events: Iterable[dict[str, Any]], *, event_type: str) -> int:
    now_ms = int(time.time() * 1000)
    day_start = now_ms - (now_ms % DEFAULT_GROWTH_SIGNALS_POLICY.day_ms)
    count = 0
    for event in events:
        try:
            if str(event.get("event_type") or "") != str(event_type):
                continue
            if int(event.get("timestamp_ms") or 0) >= day_start:
                count += 1
        except Exception:
            continue
    return count


def _top_channels(events: Iterable[dict[str, Any]], *, top_n: int) -> Iterable[str]:
    counts: dict[str, int] = {}
    for event in events:
        try:
            payload = dict(event.get("payload") or {})
        except Exception:
            payload = {}
        channel = str(payload.get("channel") or payload.get("utm_source") or payload.get("source") or "").strip().lower()
        if channel:
            counts[channel] = counts.get(channel, 0) + 1
    items = sorted(counts.items(), key=lambda item: item[1], reverse=True)[: int(top_n)]
    for channel, _count_value in items:
        yield channel


def _notes(events: Iterable[dict[str, Any]]) -> Iterable[str]:
    if _count(events, ACTION_ADS_APPLY_EXECUTE_V1) > 0:
        yield "ads_apply_used"
    if _count(events, "purchase_completed@v1") == 0:
        yield "no_purchases_recent"
    if _count(events, "lead_created@v1") == 0:
        yield "no_leads_recent"
    if _count(events, "telegram_message_in@v1") > 0:
        yield "telegram_active"


def _count(events: Iterable[dict[str, Any]], event_type: str) -> int:
    return sum(str(event.get("event_type") or "") == event_type for event in events)
