from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Tuple

from config.ads_rl_policy import DEFAULT_ADS_RL_OPT_SPEC_POLICY

Json = dict[str, Any]
Platform = Literal["meta", "yandex_direct", "vk", "telegram_ads", "unknown"]


@dataclass(frozen=True)
class AdsRLState:
    """Minimal state for ads optimization.

    Intentionally small and platform-agnostic.
    Any additional features must be added by *composition* (feature extractors),
    not by inflating this core contract.
    """

    tenant_id: str
    platform: Platform
    campaign_id: str
    ts_ms: int

    # Observed aggregate metrics for the last window (e.g., last 24h or last N hours).
    impressions: int = 0
    clicks: int = 0
    leads: int = 0
    purchases: int = 0
    spend: float = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_revenue_per_purchase
    revenue: float = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_revenue_per_purchase

    # Optional coarse context (discrete)
    day_of_week: int = 0  # 0..6
    hour_of_day: int = 0  # 0..23


@dataclass(frozen=True)
class AdsRLAction:
    """Action the optimizer proposes.

    Supports both discrete and small continuous knobs (as floats).
    """

    campaign_id: str
    # canonical knobs
    daily_budget: float | None = None
    bid_cap: float | None = None
    cpa_target: float | None = None
    # discrete choices
    creative_id: str | None = None
    audience_id: str | None = None
    objective: str | None = None

    def to_json(self) -> Json:
        return {
            "campaign_id": self.campaign_id,
            "daily_budget": self.daily_budget,
            "bid_cap": self.bid_cap,
            "cpa_target": self.cpa_target,
            "creative_id": self.creative_id,
            "audience_id": self.audience_id,
            "objective": self.objective,
        }


@dataclass(frozen=True)
class AdsRLSuggestion:
    """A suggestion is an action + safety metadata."""

    policy_id: str
    action: AdsRLAction
    confidence: float
    reason: str
    canary: bool = False
    # If allow_apply is False, caller MUST treat it as plan-only.
    allow_apply: bool = False
    safety_reason: str = ""


@dataclass(frozen=True)
class AdsRLOptSpec:
    """Optimizer request.

    This is what runtime handlers accept as payload (besides common ids).
    """

    platform: str
    campaign_id: str

    # Candidate knobs: supply *finite* sets. The optimizer chooses among them.
    daily_budgets: list[float]
    bid_caps: list[float]
    cpa_targets: list[float]
    creatives: list[str]
    audiences: list[str]
    objectives: list[str]

    # Reward configuration
    reward_mode: Literal["roas", "profit", "cpa", "cpl"] = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_reward_mode
    revenue_per_purchase: float = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_revenue_per_purchase
    value_per_lead: float = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_value_per_lead

    # Decision safety
    canary: bool = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_canary
    rollout_pct: float = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_rollout_pct
    min_history_steps: int = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_min_history_steps
    max_budget_increase_pct: float = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_max_budget_increase_pct

    window_hours: int = DEFAULT_ADS_RL_OPT_SPEC_POLICY.default_window_hours

    def validate(self) -> tuple[bool, str]:
        policy = DEFAULT_ADS_RL_OPT_SPEC_POLICY
        if not str(self.platform or "").strip():
            return False, "platform_required"
        if not str(self.campaign_id or "").strip():
            return False, "campaign_id_required"

        for name, xs in (
            ("daily_budgets", self.daily_budgets),
            ("bid_caps", self.bid_caps),
            ("cpa_targets", self.cpa_targets),
            ("creatives", self.creatives),
            ("audiences", self.audiences),
            ("objectives", self.objectives),
        ):
            if not isinstance(xs, list):
                return False, f"{name}_must_be_list"

        if self.window_hours <= 0 or self.window_hours > policy.max_window_hours:
            return False, "window_hours_out_of_range"
        if self.rollout_pct < policy.min_rollout_pct or self.rollout_pct > policy.max_rollout_pct:
            return False, "rollout_pct_out_of_range"
        if self.min_history_steps < 0 or self.min_history_steps > policy.max_history_steps:
            return False, "min_history_steps_out_of_range"
        if self.max_budget_increase_pct < policy.min_rollout_pct or self.max_budget_increase_pct > policy.max_budget_increase_pct_limit:
            return False, "max_budget_increase_pct_out_of_range"
        return True, "ok"

    def to_json(self) -> Json:
        policy = DEFAULT_ADS_RL_OPT_SPEC_POLICY
        return {
            "platform": str(self.platform),
            "campaign_id": str(self.campaign_id),
            "daily_budgets": list(self.daily_budgets or []),
            "bid_caps": list(self.bid_caps or []),
            "cpa_targets": list(self.cpa_targets or []),
            "creatives": list(self.creatives or []),
            "audiences": list(self.audiences or []),
            "objectives": list(self.objectives or []),
            "reward_mode": str(self.reward_mode),
            "revenue_per_purchase": float(self.revenue_per_purchase or policy.default_revenue_per_purchase),
            "value_per_lead": float(self.value_per_lead or policy.default_value_per_lead),
            "canary": bool(self.canary),
            "rollout_pct": float(self.rollout_pct),
            "min_history_steps": int(self.min_history_steps),
            "max_budget_increase_pct": float(self.max_budget_increase_pct),
            "window_hours": int(self.window_hours),
        }

    @staticmethod
    def from_json(obj: Json | None) -> AdsRLOptSpec:
        d: Json = obj if isinstance(obj, dict) else {}
        policy = DEFAULT_ADS_RL_OPT_SPEC_POLICY
        return AdsRLOptSpec(
            platform=str(d.get("platform") or policy.default_platform),
            campaign_id=str(d.get("campaign_id") or ""),
            daily_budgets=[float(x) for x in (d.get("daily_budgets") or []) if x is not None],
            bid_caps=[float(x) for x in (d.get("bid_caps") or []) if x is not None],
            cpa_targets=[float(x) for x in (d.get("cpa_targets") or []) if x is not None],
            creatives=[str(x) for x in (d.get("creatives") or []) if x is not None],
            audiences=[str(x) for x in (d.get("audiences") or []) if x is not None],
            objectives=[str(x) for x in (d.get("objectives") or []) if x is not None],
            reward_mode=str(d.get("reward_mode") or policy.default_reward_mode),
            revenue_per_purchase=float(d.get("revenue_per_purchase") or policy.default_revenue_per_purchase),
            value_per_lead=float(d.get("value_per_lead") or policy.default_value_per_lead),
            canary=bool(d.get("canary") if d.get("canary") is not None else policy.default_canary),
            rollout_pct=float(d.get("rollout_pct") if d.get("rollout_pct") is not None else policy.default_rollout_pct),
            min_history_steps=int(d.get("min_history_steps") if d.get("min_history_steps") is not None else policy.default_min_history_steps),
            max_budget_increase_pct=float(
                d.get("max_budget_increase_pct")
                if d.get("max_budget_increase_pct") is not None
                else policy.default_max_budget_increase_pct
            ),
            window_hours=int(d.get("window_hours") if d.get("window_hours") is not None else policy.default_window_hours),
        )


def action_from_json(obj: Json | None) -> AdsRLAction:
    d: Json = obj if isinstance(obj, dict) else {}
    return AdsRLAction(
        campaign_id=str(d.get("campaign_id") or ""),
        daily_budget=_float_or_none(d.get("daily_budget")),
        bid_cap=_float_or_none(d.get("bid_cap")),
        cpa_target=_float_or_none(d.get("cpa_target")),
        creative_id=str(d.get("creative_id") or "") or None,
        audience_id=str(d.get("audience_id") or "") or None,
        objective=str(d.get("objective") or "") or None,
    )


def _float_or_none(x: object) -> float | None:
    if x is None:
        return None
    try:
        return float(x)  # type: ignore[arg-type]
    except Exception:
        return None
