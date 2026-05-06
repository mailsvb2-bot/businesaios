from __future__ import annotations

from config.final_hidden_logic_policy import DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY
from core.strategic_horizon.constants import MAX_RISK_BUDGET, MIN_RISK_BUDGET


def select_horizon(mode) -> int:
    from core.strategic_horizon.engine import StrategicMode

    return {
        StrategicMode.DEFENSE: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.horizon_days_defense,
        StrategicMode.STABILIZE: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.horizon_days_stabilize,
        StrategicMode.OPTIMIZE: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.horizon_days_optimize,
        StrategicMode.EXPAND: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.horizon_days_expand,
        StrategicMode.RESEARCH: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.horizon_days_research,
    }[mode]


def compute_risk_budget(s, mode) -> float:
    from core.strategic_horizon.engine import StrategicMode

    base = DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.budget_baseline - max(s.risk.financial_risk, s.risk.ux_risk, s.risk.regulatory_risk)
    mode_multiplier = {
        StrategicMode.DEFENSE: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.defense_budget_multiplier,
        StrategicMode.STABILIZE: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.stabilize_budget_multiplier,
        StrategicMode.OPTIMIZE: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.optimize_budget_multiplier,
        StrategicMode.EXPAND: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.expand_budget_multiplier,
        StrategicMode.RESEARCH: DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.research_budget_multiplier,
    }[mode]
    risk = base * mode_multiplier
    return float(min(MAX_RISK_BUDGET, max(MIN_RISK_BUDGET, risk)))


def growth_pressure(s, mode) -> float:
    from core.strategic_horizon.engine import StrategicMode

    if mode in (StrategicMode.DEFENSE, StrategicMode.STABILIZE):
        return DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.growth_pressure_defense
    signal = (
        DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.growth_rate_weight * s.product.growth_rate
        + DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.margin_weight * s.economy.margin
        + DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.churn_inverse_weight * (DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.one_value - s.product.churn_rate)
    )
    if mode == StrategicMode.EXPAND:
        signal *= DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.expand_signal_multiplier
    return float(max(DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.zero_value, min(DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.one_value, signal)))


def learning_regime(s, mode):
    from core.strategic_horizon.engine import LearningRegime, StrategicMode

    if mode == StrategicMode.DEFENSE:
        return LearningRegime.FROZEN
    if s.learning.offline_score < DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.frozen_offline_score_ceiling:
        return LearningRegime.FROZEN
    if mode == StrategicMode.EXPAND and s.learning.online_reward_confidence > DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY.aggressive_online_confidence_threshold:
        return LearningRegime.AGGRESSIVE
    return LearningRegime.SAFE
