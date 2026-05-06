from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config.ads_policy_defaults import (
    DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS,
    AdsAutopilotPolicyDefaults,
)


class AdsMode(str, Enum):
    READ_ONLY = "read_only"
    RECOMMENDATIONS = "recommendations"
    AUTOPILOT = "autopilot"


@dataclass(frozen=True)
class AutopilotLimits:
    max_daily_spend_delta_pct: float = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS.max_daily_spend_delta_pct
    max_bid_delta_pct: float = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS.max_bid_delta_pct
    max_budget_per_campaign: float = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS.max_budget_per_campaign
    require_human_approval_for_creative: bool = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS.require_human_approval_for_creative
    change_window_utc_start: int = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS.change_window_utc_start
    change_window_utc_end: int = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS.change_window_utc_end


@dataclass(frozen=True)
class AdsEntitlements:
    mode: AdsMode = AdsMode.READ_ONLY
    limits: AutopilotLimits = field(default_factory=AutopilotLimits)
    approver_user_id: Optional[str] = None
    policy_defaults: AdsAutopilotPolicyDefaults = DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS


class AdsPolicy:
    def __init__(self, entitlements: AdsEntitlements):
        self._ent = entitlements

    def mode(self) -> AdsMode:
        return self._ent.mode

    def assert_write_allowed(self) -> None:
        if self._ent.mode == AdsMode.READ_ONLY:
            raise PermissionError("Ads mode is READ_ONLY")

    def assert_autopilot_allowed(self) -> None:
        if self._ent.mode != AdsMode.AUTOPILOT:
            raise PermissionError("Ads mode is not AUTOPILOT")
