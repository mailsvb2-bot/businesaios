from __future__ import annotations

from config.final_hidden_logic_policy import DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY
from core.strategic_horizon.constants import MIN_MARGIN_SAFE, MIN_RUNWAY_DEFENSE, MIN_RUNWAY_STABILIZE


def infer_mode(s):
    from core.strategic_horizon.engine import StrategicMode

    if is_defense(s):
        return StrategicMode.DEFENSE
    if is_unstable(s):
        return StrategicMode.STABILIZE
    if can_expand(s):
        return StrategicMode.EXPAND
    if can_optimize(s):
        return StrategicMode.OPTIMIZE
    return StrategicMode.RESEARCH


def is_defense(s) -> bool:
    return (
        s.economy.cash_runway_days < MIN_RUNWAY_DEFENSE
        or s.risk.financial_risk > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.financial_risk_defense_threshold
        or s.learning.policy_divergence > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.policy_divergence_defense_threshold
    )


def is_unstable(s) -> bool:
    return (
        s.economy.cash_runway_days < MIN_RUNWAY_STABILIZE
        or s.economy.margin < MIN_MARGIN_SAFE
        or s.product.churn_rate > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.churn_unstable_threshold
    )


def can_expand(s) -> bool:
    return (
        s.economy.margin > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.margin_expand_threshold
        and s.product.growth_rate > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.growth_expand_threshold
        and s.learning.offline_score > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.offline_score_expand_threshold
        and s.risk.financial_risk < DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.financial_risk_expand_ceiling
    )


def can_optimize(s) -> bool:
    return (
        s.economy.margin > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.margin_optimize_threshold
        and s.learning.online_reward_confidence > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.online_reward_confidence_optimize_threshold
        and s.risk.financial_risk < DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.financial_risk_optimize_ceiling
    )
