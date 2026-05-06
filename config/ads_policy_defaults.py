from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class AdsAutopilotPolicyDefaults:
    max_daily_spend_delta_pct: float = 10.0
    max_bid_delta_pct: float = 10.0
    max_budget_per_campaign: float = 50.0
    require_human_approval_for_creative: bool = True
    change_window_utc_start: int = 6
    change_window_utc_end: int = 20


DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS = AdsAutopilotPolicyDefaults()
