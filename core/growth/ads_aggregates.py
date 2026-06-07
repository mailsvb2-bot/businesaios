from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol
from collections.abc import Iterable

from config.ads_aggregates_policy import DEFAULT_ADS_AGGREGATES_POLICY, AdsAggregatesPolicy


class EventStore(Protocol):
    def latest_events(
        self,
        *,
        tenant_id: str,
        event_type: str,
        limit: int = DEFAULT_ADS_AGGREGATES_POLICY.latest_events_limit,
    ) -> Iterable[dict[str, Any]]: ...


@dataclass
class DailyAgg:
    impressions: int = DEFAULT_ADS_AGGREGATES_POLICY.default_impressions
    clicks: int = DEFAULT_ADS_AGGREGATES_POLICY.default_clicks
    spend: float = DEFAULT_ADS_AGGREGATES_POLICY.default_spend
    conversions: int = DEFAULT_ADS_AGGREGATES_POLICY.default_conversions
    revenue: float = DEFAULT_ADS_AGGREGATES_POLICY.default_revenue

    def cpa(self) -> float | None:
        return (self.spend / self.conversions) if self.conversions > int(DEFAULT_ADS_AGGREGATES_POLICY.default_conversions) else None

    def roas(self, *, policy: AdsAggregatesPolicy | None = None) -> float | None:
        policy = policy or DEFAULT_ADS_AGGREGATES_POLICY
        return (self.revenue / self.spend) if self.spend > float(policy.min_spend_for_roas) else None


class AdsAggregates:
    def __init__(self, store: EventStore, *, policy: AdsAggregatesPolicy | None = None):
        self._store = store
        self._policy = policy or DEFAULT_ADS_AGGREGATES_POLICY

    def by_campaign_day(self, *, tenant_id: str, day_iso: str) -> dict[str, DailyAgg]:
        out: dict[str, DailyAgg] = {}
        for ev in self._store.latest_events(
            tenant_id=tenant_id,
            event_type="ads_metrics_imported",
            limit=int(self._policy.latest_events_limit),
        ):
            p = ev.get("payload") or {}
            ref = p.get("ref") or {}
            if str(ref.get("day")) != day_iso:
                continue
            if str(ref.get("object_type")) != "campaign":
                continue
            cid = str(ref.get("object_id") or "")
            m = p.get("metrics") or {}
            agg = out.get(cid) or DailyAgg()
            agg.impressions += int(m.get("impressions") or int(self._policy.default_impressions))
            agg.clicks += int(m.get("clicks") or int(self._policy.default_clicks))
            agg.spend += float(m.get("spend") or float(self._policy.default_spend))
            agg.conversions += int(m.get("conversions") or int(self._policy.default_conversions))
            agg.revenue += float(m.get("revenue") or float(self._policy.default_revenue))
            out[cid] = agg
        return out
