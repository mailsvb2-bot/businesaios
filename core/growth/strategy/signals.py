from __future__ import annotations

import logging
import time
from typing import Any, Iterable

from config.strategic_growth_policy import DEFAULT_GROWTH_SIGNALS_POLICY, GrowthSignalsPolicy
from core.actions.names import ACTION_ADS_APPLY_EXECUTE_V1
from core.growth.today_ledger import build_today_kpi
from core.observability.errors import log_exception_throttled

from .contracts import GrowthSignalV1

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
    for ev in events:
        try:
            uid = str(ev.get("user_id") or "")
            ts = int(ev.get("timestamp_ms") or 0)
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

    channels = tuple(_top_channels(events, top_n=policy.top_channels_limit))
    notes = tuple(_notes(events))

    return GrowthSignalV1(
        ts_ms=now_ms,
        tenant_id=str(tenant_id),
        leads_today=int(kpi.leads),
        spend_today_minor=int(kpi.spend_minor),
        revenue_today_minor=int(kpi.revenue_minor),
        profit_today_minor=int(kpi.profit_minor),
        retention_d1_pct=float(round(d1, 2)),
        retention_d7_pct=float(round(d7, 2)),
        conversion_lead_to_purchase_pct=float(round(conv, 2)),
        top_channels=channels,
        notes=notes,
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

    for et in policy.common_event_types:
        yield from _latest_events(
            event_store,
            tenant_id=tenant_id,
            event_type=et,
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
    c = 0
    for e in events:
        try:
            if str(e.get("event_type") or "") != str(event_type):
                continue
            ts = int(e.get("timestamp_ms") or 0)
            if ts >= day_start:
                c += 1
        except Exception:
            continue
    return int(c)


def _top_channels(events: Iterable[dict[str, Any]], *, top_n: int) -> Iterable[str]:
    counts: dict[str, int] = {}
    for e in events:
        try:
            p = dict(e.get("payload") or {})
        except Exception:
            p = {}
        ch = str(p.get("channel") or p.get("utm_source") or p.get("source") or "").strip().lower()
        if not ch:
            continue
        counts[ch] = counts.get(ch, 0) +1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[: int(top_n)]
    for k, _ in items:
        yield k


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
    c = 0
    for e in events:
        if str(e.get("event_type") or "") == str(event_type):
            c += 1
    return int(c)
