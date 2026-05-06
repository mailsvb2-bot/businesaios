from __future__ import annotations

"""Compatibility wrapper to the canonical ledger_v2 read-model."""

from dataclasses import dataclass
from typing import Any

from core.growth.ledger_v2 import snapshot_today


@dataclass(frozen=True)
class TodayGrowthKPI:
    leads: int
    spend_minor: int
    revenue_minor: int
    profit_minor: int


def build_today_kpi(event_store: Any, *, tenant_id: str, **_: Any) -> TodayGrowthKPI:
    snap = snapshot_today(event_store=event_store, tenant_id=str(tenant_id))
    return TodayGrowthKPI(
        leads=int(snap.leads),
        spend_minor=int(snap.spend_minor),
        revenue_minor=int(snap.revenue_minor),
        profit_minor=int(snap.profit_minor),
    )
