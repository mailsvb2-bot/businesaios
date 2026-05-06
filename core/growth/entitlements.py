from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from config.growth_entitlements_policy import DEFAULT_GROWTH_ENTITLEMENTS_POLICY, GrowthEntitlementsPolicy
from core.ads.policy import AdsEntitlements, AdsMode, AutopilotLimits

@dataclass(frozen=True)
class DailyLimits:
    max_spend_total: float = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_max_spend_total
    max_spend_per_platform: float = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_max_spend_per_platform
    max_spend_per_campaign: float = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_max_spend_per_campaign
    max_budget_increase_pct: float = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_max_daily_spend_delta_pct
    allow_creative_changes: bool = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_allow_creative_changes
    change_window_utc_start: int = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_change_window_utc_start
    change_window_utc_end: int = DEFAULT_GROWTH_ENTITLEMENTS_POLICY.default_change_window_utc_end

class TenantConfigStore(Protocol):
    def get(self, *, tenant_id: str, key: str) -> Optional[str]: ...

class GrowthEntitlementsProvider:
    def __init__(self, store: TenantConfigStore, *, policy: GrowthEntitlementsPolicy = DEFAULT_GROWTH_ENTITLEMENTS_POLICY):
        self._store = store
        self._policy = policy

    def get_ads_entitlements(self, tenant_id: str) -> AdsEntitlements:
        mode_s = (self._store.get(tenant_id=tenant_id, key="ads.mode") or self._policy.default_ads_mode).strip().lower()
        mode = AdsMode.READ_ONLY
        if mode_s == "recommendations":
            mode = AdsMode.RECOMMENDATIONS
        elif mode_s == "autopilot":
            mode = AdsMode.AUTOPILOT
        return AdsEntitlements(
            mode=mode,
            limits=AutopilotLimits(
                max_daily_spend_delta_pct=float(self._store.get(tenant_id=tenant_id, key="ads.autopilot.max_daily_spend_delta_pct") or self._policy.default_max_daily_spend_delta_pct),
                max_bid_delta_pct=float(self._store.get(tenant_id=tenant_id, key="ads.autopilot.max_bid_delta_pct") or self._policy.default_max_bid_delta_pct),
                max_budget_per_campaign=float(self._store.get(tenant_id=tenant_id, key="ads.autopilot.max_budget_per_campaign") or self._policy.default_max_budget_per_campaign),
                require_human_approval_for_creative=(self._store.get(tenant_id=tenant_id, key="ads.autopilot.require_human_approval_for_creative") or self._policy.true_token).lower() == self._policy.true_token,
                change_window_utc_start=int(self._store.get(tenant_id=tenant_id, key="ads.autopilot.change_window_utc_start") or self._policy.default_change_window_utc_start),
                change_window_utc_end=int(self._store.get(tenant_id=tenant_id, key="ads.autopilot.change_window_utc_end") or self._policy.default_change_window_utc_end),
            ),
            approver_user_id=self._store.get(tenant_id=tenant_id, key="ads.approver_user_id"),
        )

    def get_daily_limits(self, tenant_id: str) -> DailyLimits:
        return DailyLimits(
            max_spend_total=float(self._store.get(tenant_id=tenant_id, key="ads.limits.max_spend_total") or self._policy.default_max_spend_total),
            max_spend_per_platform=float(self._store.get(tenant_id=tenant_id, key="ads.limits.max_spend_per_platform") or self._policy.default_max_spend_per_platform),
            max_spend_per_campaign=float(self._store.get(tenant_id=tenant_id, key="ads.limits.max_spend_per_campaign") or self._policy.default_max_spend_per_campaign),
            max_budget_increase_pct=float(self._store.get(tenant_id=tenant_id, key="ads.limits.max_budget_increase_pct") or self._policy.default_max_daily_spend_delta_pct),
            allow_creative_changes=(self._store.get(tenant_id=tenant_id, key="ads.limits.allow_creative_changes") or "false").lower() == self._policy.true_token,
            change_window_utc_start=int(self._store.get(tenant_id=tenant_id, key="ads.limits.change_window_utc_start") or self._policy.default_change_window_utc_start),
            change_window_utc_end=int(self._store.get(tenant_id=tenant_id, key="ads.limits.change_window_utc_end") or self._policy.default_change_window_utc_end),
        )
