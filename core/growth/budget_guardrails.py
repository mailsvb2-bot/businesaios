from __future__ import annotations

"""Budget guardrails.

Even when Ads Connector is enabled, budget is enforced here.
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from config.growth_budget_guardrails_policy import (
    DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY,
    GrowthBudgetGuardrailsPolicy,
)


@dataclass(frozen=True)
class BudgetPolicy:
    daily_budget_minor: int
    currency: str = "RUB"
    stop_on_exceed: bool = True
    policy: GrowthBudgetGuardrailsPolicy = DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY

    def validate(self) -> None:
        if int(self.daily_budget_minor) < 0:
            raise ValueError("daily_budget_minor must be >= 0")
        if not str(self.currency or "").strip():
            raise ValueError("currency is required")


@dataclass(frozen=True)
class BudgetVerdict:
    allow: bool
    reason: str
    spend_minor: int = 0
    limit_minor: int = 0


def enforce_daily_budget(*, policy: BudgetPolicy, spend_minor_today: int) -> BudgetVerdict:
    policy.validate()
    spend = int(spend_minor_today)
    limit = int(policy.daily_budget_minor)
    policy_cfg = policy.policy
    if limit <= 0:
        return BudgetVerdict(True, policy_cfg.no_budget_limit_reason, spend_minor=spend, limit_minor=limit)
    if spend <= limit:
        return BudgetVerdict(True, policy_cfg.ok_reason, spend_minor=spend, limit_minor=limit)
    return BudgetVerdict(False, policy_cfg.daily_budget_exceeded_reason, spend_minor=spend, limit_minor=limit)


# ---- Ads write guardrails (Stage 2/3) ----

from dataclasses import dataclass as _dc
from datetime import UTC, datetime, timezone
from typing import Optional, Protocol


class EventSink(Protocol):
    def emit(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: dict) -> None: ...


@_dc(frozen=True)
class DailyLimits:
    """Hard rails for ads spend and changes."""

    max_spend_total: float
    max_spend_per_platform: float
    max_spend_per_campaign: float
    max_budget_increase_pct: float = DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY.max_budget_increase_pct
    allow_creative_changes: bool = DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY.allow_creative_changes
    change_window_utc_start: int = DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY.change_window_utc_start
    change_window_utc_end: int = DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY.change_window_utc_end
    policy: GrowthBudgetGuardrailsPolicy = DEFAULT_GROWTH_BUDGET_GUARDRAILS_POLICY


class SpendLedger(Protocol):
    def get_spend_today_total(self, *, tenant_id: str) -> float: ...
    def get_spend_today_platform(self, *, tenant_id: str, platform: str) -> float: ...
    def get_spend_today_campaign(self, *, tenant_id: str, platform: str, campaign_id: str) -> float: ...


class BudgetGuardrails:
    """Canonical guardrails.

    This module is the only place that answers "is this write allowed?".
    Any future ads mutation must call it.
    """

    def __init__(self, *, limits: DailyLimits, ledger: SpendLedger, sink: EventSink):
        self._limits = limits
        self._ledger = ledger
        self._sink = sink

    def assert_time_window(self, *, tenant_id: str) -> None:
        now = datetime.now(UTC)
        if not (self._limits.change_window_utc_start <= now.hour < self._limits.change_window_utc_end):
            raise PermissionError("Change is outside allowed time window.")

    def assert_budget_change_allowed(
        self,
        *,
        tenant_id: str,
        platform: str,
        campaign_id: str,
        patch: Mapping[str, Any],
    ) -> None:
        spend_floor = self._limits.policy.zero_spend_floor
        total = max(spend_floor, float(self._ledger.get_spend_today_total(tenant_id=tenant_id)))
        plat = max(spend_floor, float(self._ledger.get_spend_today_platform(tenant_id=tenant_id, platform=platform)))
        camp = max(spend_floor, float(self._ledger.get_spend_today_campaign(tenant_id=tenant_id, platform=platform, campaign_id=campaign_id)))

        if total >= self._limits.max_spend_total:
            self._emit_block(tenant_id, platform, campaign_id, "max_spend_total reached", {"total": total})
            raise PermissionError("Daily total spend limit reached.")
        if plat >= self._limits.max_spend_per_platform:
            self._emit_block(tenant_id, platform, campaign_id, "max_spend_per_platform reached", {"platform_spend": plat})
            raise PermissionError("Daily platform spend limit reached.")
        if camp >= self._limits.max_spend_per_campaign:
            self._emit_block(tenant_id, platform, campaign_id, "max_spend_per_campaign reached", {"campaign_spend": camp})
            raise PermissionError("Daily campaign spend limit reached.")

        if "daily_budget_delta_pct" in patch:
            try:
                delta = float(patch["daily_budget_delta_pct"])  # type: ignore[index]
            except Exception:
                raise PermissionError("Invalid daily_budget_delta_pct.")
            if delta > self._limits.max_budget_increase_pct:
                self._emit_block(tenant_id, platform, campaign_id, "budget increase too high", {"delta_pct": delta})
                raise PermissionError("Budget increase exceeds max_budget_increase_pct.")

        if patch.get("creative_update") and not self._limits.allow_creative_changes:
            self._emit_block(tenant_id, platform, campaign_id, "creative changes disabled", {})
            raise PermissionError("Creative changes are disabled by guardrails.")

    def _emit_block(self, tenant_id: str, platform: str, campaign_id: str, reason: str, extra: dict) -> None:
        self._sink.emit(
            tenant_id=tenant_id,
            user_id=None,
            event_type=self._limits.policy.ads_guardrails_block_event_type,
            payload={"platform": platform, "campaign_id": campaign_id, "reason": reason, **(extra or {})},
        )
