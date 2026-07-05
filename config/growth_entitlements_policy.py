from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class GrowthEntitlementsPolicy:
    default_ads_mode: str = "read_only"
    default_max_spend_total: float = 100.0
    default_max_spend_per_platform: float = 60.0
    default_max_spend_per_campaign: float = 30.0
    default_max_daily_spend_delta_pct: float = 10.0
    default_max_bid_delta_pct: float = 10.0
    default_max_budget_per_campaign: float = 50.0
    default_allow_creative_changes: bool = False
    default_require_human_approval_for_creative: bool = True
    default_change_window_utc_start: int = 6
    default_change_window_utc_end: int = 20
    true_token: str = "true"


DEFAULT_GROWTH_ENTITLEMENTS_POLICY = GrowthEntitlementsPolicy()


__all__ = ["GrowthEntitlementsPolicy", "DEFAULT_GROWTH_ENTITLEMENTS_POLICY"]
