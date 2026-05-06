from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class AdsAggregatesPolicy:
    latest_events_limit: int = 10000
    min_spend_for_roas: float = 1e-9
    default_impressions: int = 0
    default_clicks: int = 0
    default_conversions: int = 0
    default_spend: float = 0.0
    default_revenue: float = 0.0


DEFAULT_ADS_AGGREGATES_POLICY = AdsAggregatesPolicy()
