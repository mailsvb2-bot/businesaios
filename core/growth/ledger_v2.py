"""Unified Growth Ledger v2 (range-capable read-model).

This does NOT replace existing read-models; it's an additive primitive.
Goal: provide ONE small API for money KPIs used by dashboards / AI modules.

Event contracts (default names):
  - lead_created@v1
  - purchase_completed@v1 payload.amount_minor
  - refund_completed@v1 payload.amount_minor
  - cogs_recorded@v1 payload.amount_minor (optional)

This module is intentionally tolerant: missing events => zeros.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from core.events.read_call import call_iter_events, call_latest_events
from core.growth.spend_ledger_event_store import EventStoreSpendLedger
from core.observability.structured_logging import log_exception_throttled


def _day_start_ms(ts_ms: int) -> int:
    return ts_ms - (ts_ms % 86_400_000)


@dataclass(frozen=True)
class GrowthSnapshot:
    leads: int
    spend_minor: int
    revenue_minor: int
    refunds_minor: int
    cogs_minor: int

    profit_minor: int
    margin_minor: int
    cashflow_minor: int


def snapshot_today(*, event_store: Any, tenant_id: str) -> GrowthSnapshot:
    now_ms = int(time.time() * 1000)
    start = _day_start_ms(now_ms)
    return snapshot_range(event_store=event_store, tenant_id=str(tenant_id), start_ms=int(start), end_ms=int(now_ms))


def snapshot_7d(*, event_store: Any, tenant_id: str) -> GrowthSnapshot:
    now_ms = int(time.time() * 1000)
    start = int(now_ms) - 7 * 86_400_000
    return snapshot_range(event_store=event_store, tenant_id=str(tenant_id), start_ms=start, end_ms=now_ms)


def snapshot_range(
    *,
    event_store: Any,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    lead_event_type: str = "lead_created@v1",
    purchase_event_type: str = "purchase_completed@v1",
    refund_event_type: str = "refund_completed@v1",
    cogs_event_type: str = "cogs_recorded@v1",
) -> GrowthSnapshot:
    leads = _count_events(event_store, tenant_id=tenant_id, event_type=lead_event_type, start_ms=start_ms, end_ms=end_ms)
    revenue = _sum_minor(event_store, tenant_id=tenant_id, event_type=purchase_event_type, start_ms=start_ms, end_ms=end_ms, key="amount_minor")
    refunds = _sum_minor(event_store, tenant_id=tenant_id, event_type=refund_event_type, start_ms=start_ms, end_ms=end_ms, key="amount_minor")
    cogs = _sum_minor(event_store, tenant_id=tenant_id, event_type=cogs_event_type, start_ms=start_ms, end_ms=end_ms, key="amount_minor")

    spend = EventStoreSpendLedger(event_store).spend_minor_range(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms)

    profit = int(revenue) - int(refunds) - int(spend) - int(cogs)
    margin = int(revenue) - int(refunds) - int(cogs)
    cashflow = int(revenue) - int(refunds) - int(spend)

    return GrowthSnapshot(
        leads=int(leads),
        spend_minor=int(spend),
        revenue_minor=int(revenue),
        refunds_minor=int(refunds),
        cogs_minor=int(cogs),
        profit_minor=int(profit),
        margin_minor=int(margin),
        cashflow_minor=int(cashflow),
    )


def _iter_events(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int,
    end_ms: int,
    limit: int = 5000,
) -> Iterable[dict[str, Any]]:
    it = getattr(event_store, "iter_events", None)
    if callable(it):
        yield from call_iter_events(
            iter_fn=it,
            tenant_id=str(tenant_id),
            event_types=(str(event_type),),
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            limit=int(limit),
            user_id=None,
        )
        return
    latest = getattr(event_store, "latest_events", None)
    if callable(latest):
        yield from call_latest_events(
            latest_fn=latest,
            tenant_id=str(tenant_id),
            event_types=(str(event_type),),
            limit=int(limit),
        ) or []


def _event_ts_ms(e: dict[str, Any]) -> int:
    try:
        return int(e.get("timestamp_ms") or 0)
    except Exception:
        return 0


def _count_events(event_store: Any, *, tenant_id: str, event_type: str, start_ms: int, end_ms: int) -> int:
    n = 0
    for e in _iter_events(event_store, tenant_id=tenant_id, event_type=event_type, start_ms=start_ms, end_ms=end_ms):
        ts = _event_ts_ms(e if isinstance(e, dict) else {})
        if int(start_ms) <= ts <= int(end_ms):
            n += 1
    return int(n)


def _sum_minor(event_store: Any, *, tenant_id: str, event_type: str, start_ms: int, end_ms: int, key: str) -> int:
    total = 0
    for e in _iter_events(event_store, tenant_id=tenant_id, event_type=event_type, start_ms=start_ms, end_ms=end_ms):
        if not isinstance(e, dict):
            continue
        ts = _event_ts_ms(e)
        if ts < int(start_ms) or ts > int(end_ms):
            continue
        payload = e.get("payload")
        if not isinstance(payload, dict):
            continue
        v = payload.get(key)
        try:
            total += int(v or 0)
        except Exception as exc:
            log_exception_throttled(__name__, "growth_ledger_amount_minor_parse_failed", exc)
    return int(total)
