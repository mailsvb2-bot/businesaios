from __future__ import annotations

"""Growth Ledger adapter for AI CEO (read-only).

AI CEO relies on ONE source of truth for money + growth KPIs.
This adapter deliberately stays tiny and tolerant to missing sources.

It may read from:
- core.growth.today_ledger (today read-model)
- event_store spend ledger
- optional revenue events

No side-effects.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.growth.today_ledger import build_today_kpi


@dataclass(frozen=True)
class GrowthSnapshotV1:
    schema_version: int = 1
    leads: int = 0
    spend_minor: int = 0
    revenue_minor: int = 0
    profit_minor: int = 0


def read_growth_snapshot(event_store: Any, *, tenant_id: str) -> GrowthSnapshotV1:
    try:
        k = build_today_kpi(event_store, tenant_id=str(tenant_id))
        return GrowthSnapshotV1(
            leads=int(k.leads),
            spend_minor=int(k.spend_minor),
            revenue_minor=int(k.revenue_minor),
            profit_minor=int(k.profit_minor),
        )
    except Exception:
        # tolerate absent event store in tests / demo
        return GrowthSnapshotV1()


def to_dict(s: GrowthSnapshotV1) -> dict[str, int]:
    return {
        "leads": int(s.leads),
        "spend_minor": int(s.spend_minor),
        "revenue_minor": int(s.revenue_minor),
        "profit_minor": int(s.profit_minor),
    }
