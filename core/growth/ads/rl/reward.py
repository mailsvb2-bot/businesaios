from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Tuple

from config.ads_rl_policy import DEFAULT_ADS_RL_REWARD_POLICY, AdsRLRewardPolicy

from .contracts import AdsRLOptSpec, AdsRLState


@dataclass(frozen=True)
class RewardBreakdown:
    reward: float
    mode: str
    components: Dict[str, float]


def compute_reward(*, state: AdsRLState, spec: AdsRLOptSpec, policy: AdsRLRewardPolicy = DEFAULT_ADS_RL_REWARD_POLICY) -> RewardBreakdown:
    """Compute scalar reward from observed window metrics.

    Important:
    - reward is computed from *observations*, not from beliefs.
    - caller must ensure `state` corresponds to the intended evaluation window.
    """
    spend = float(state.spend or policy.zero_reward)
    revenue = float(state.revenue or policy.zero_reward)

    leads = int(state.leads or 0)
    purchases = int(state.purchases or 0)

    mode = str(spec.reward_mode or policy.reward_mode_profit)
    if mode == policy.reward_mode_roas:
        roas = revenue / spend if spend > 0 else (policy.zero_reward if revenue <= 0 else policy.roas_when_no_spend_with_revenue)
        return RewardBreakdown(float(roas), policy.reward_mode_roas, {"roas": float(roas), "revenue": revenue, "spend": spend})

    if mode == policy.reward_mode_profit:
        # If revenue is missing, estimate from purchases / leads.
        est_revenue = revenue
        if est_revenue <= policy.zero_reward and purchases > 0 and float(spec.revenue_per_purchase or policy.zero_reward) > 0:
            est_revenue = float(purchases) * float(spec.revenue_per_purchase)
        if est_revenue <= policy.zero_reward and leads > 0 and float(spec.value_per_lead or policy.zero_reward) > 0:
            est_revenue = float(leads) * float(spec.value_per_lead)
        profit = est_revenue - spend
        return RewardBreakdown(float(profit), policy.reward_mode_profit, {"profit": float(profit), "est_revenue": float(est_revenue), "spend": spend})

    if mode == policy.reward_mode_cpa:
        # Lower CPA is better => negative cpa.
        if purchases <= 0:
            return RewardBreakdown(-float(spend), policy.reward_mode_cpa, {"purchases": float(purchases), "spend": spend})
        cpa = spend / float(purchases)
        return RewardBreakdown(-float(cpa), policy.reward_mode_cpa, {"cpa": float(cpa), "purchases": float(purchases), "spend": spend})

    if mode == policy.reward_mode_cpl:
        if leads <= 0:
            return RewardBreakdown(-float(spend), policy.reward_mode_cpl, {"leads": float(leads), "spend": spend})
        cpl = spend / float(leads)
        return RewardBreakdown(-float(cpl), policy.reward_mode_cpl, {"cpl": float(cpl), "leads": float(leads), "spend": spend})

    # Fallback: profit-like.
    profit = revenue - spend
    return RewardBreakdown(float(profit), policy.reward_mode_profit_fallback, {"profit": float(profit), "revenue": revenue, "spend": spend})
