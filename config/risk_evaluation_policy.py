from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class IncrementalityPolicy:
    missing_stderr_confidence_fallback: float = 0.45
    minimum_score: float = 0.0
    maximum_score: float = 1.0
    negative_effect_multiplier: float = 1.0
    downside_confidence_weight: float = 1.0


@dataclass(frozen=True)
class UncertaintyPenaltyPolicy:
    causal_gap_weight: float = 0.45
    experiment_gap_weight: float = 0.35
    downside_weight: float = 0.20
    minimum_score: float = 0.0
    maximum_score: float = 1.0


@dataclass(frozen=True)
class RiskCostPolicy:
    downside_envelope_weight: float = 0.40
    architecture_instability_weight: float = 0.25
    blast_radius_risk_weight: float = 0.20
    flow_turbulence_weight: float = 0.15
    minimum_score: float = 0.0
    maximum_score: float = 1.0


@dataclass(frozen=True)
class EscalationRiskPolicy:
    base_score_by_level: Mapping[str, float] = field(
        default_factory=lambda: {"critical": 0.80, "high": 0.50, "medium": 0.25}
    )
    paused_status_addon: float = 0.15
    override_applied_addon: float = 0.20
    score_ceiling: float = 1.0


@dataclass(frozen=True)
class ExperimentRiskPolicy:
    insufficient_exposure_level: str = "high"
    negative_uplift_level: str = "high"
    medium_p_value_threshold: float = 0.10
    low_p_value_threshold: float = 0.05
    medium_level: str = "medium"
    low_level: str = "low"
    require_positive_uplift_for_low_risk: bool = True


@dataclass(frozen=True)
class LiquidityRiskPolicy:
    negative_cash_risk: float = 1.0
    no_reserve_target_risk: float = 0.0
    severe_ratio_threshold: str = "0.5"
    severe_ratio_risk: float = 0.75
    warning_ratio_threshold: str = "1"
    warning_ratio_risk: float = 0.4
    healthy_ratio_risk: float = 0.0


@dataclass(frozen=True)
class StopLossDefaultsPolicy:
    enabled: bool = False
    lookback_hours: int = 24
    min_trials: int = 20
    cooldown_hours: int = 6
    cooldown_max_hours: int = 24
    cooldown_backoff_lookback_hours: int = 72
    cooldown_decay_enabled: bool = False
    max_conv_drop_pct: float = 0.20
    max_rev_drop_pct: float = 0.20


@dataclass(frozen=True)
class FraudPatternRiskPolicy:
    duplicate_hit_weight: float = 0.15
    velocity_weight: float = 0.35
    source_spoof_weight: float = 0.35
    high_velocity_threshold: float = 0.5
    source_spoof_threshold: float = 0.5
    customer_fit_rank_floor: float = 0.20
    score_ceiling: float = 1.0


@dataclass(frozen=True)
class FraudRiskTrackerPolicy:
    fraud_flag_weight: float = 0.70
    duplicate_flag_weight: float = 0.20
    source_spoof_flag_weight: float = 0.20
    existing_customer_flag_weight: float = 0.15
    high_penalty_threshold: float = 0.90
    medium_penalty_threshold: float = 0.70
    low_penalty_threshold: float = 0.40
    high_penalty: float = 1.0
    medium_penalty: float = 0.9
    low_penalty: float = 0.4
    zero_penalty: float = 0.0
    score_ceiling: float = 1.0


@dataclass(frozen=True)
class EconomicRiskEnvelopePolicy:
    medium_confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.25
    medium_downside_threshold: float = 0.0
    high_downside_threshold: float = -0.25


@dataclass(frozen=True)
class PerformanceFeedbackLearningPolicy:
    blocked_verification_floor: float = 0.35
    month_goal_achievement_threshold: float = 0.60
    month_verification_threshold: float = 0.65
    month_cost_efficiency_threshold: float = 0.50
    week_goal_achievement_threshold: float = 0.35
    week_verification_threshold: float = 0.45
    checkpoint_verify_before_scale_threshold: float = 0.45


@dataclass(frozen=True)
class CanonicalDecisionBridgePolicy:
    base_confidence: float = 0.5
    adjusted_confidence_weight: float = 0.5
    minimum_score: float = 0.0
    maximum_score: float = 1.0


@dataclass(frozen=True)
class CapabilityDiagnosticsPolicy:
    low_confidence_threshold: float = 0.35


@dataclass(frozen=True)
class PerformanceProfilePolicy:
    route_state_weight_floor: float = 0.05
    budget_multiplier_floor: float = 0.25
    budget_multiplier_ceiling: float = 3.0
    spend_tightness_default: float = 0.5
    min_expected_roi_default: float = 0.25


DEFAULT_INCREMENTALITY_POLICY = IncrementalityPolicy()
DEFAULT_UNCERTAINTY_PENALTY_POLICY = UncertaintyPenaltyPolicy()
DEFAULT_RISK_COST_POLICY = RiskCostPolicy()
DEFAULT_ESCALATION_RISK_POLICY = EscalationRiskPolicy()
DEFAULT_EXPERIMENT_RISK_POLICY = ExperimentRiskPolicy()
DEFAULT_LIQUIDITY_RISK_POLICY = LiquidityRiskPolicy()
DEFAULT_STOP_LOSS_DEFAULTS_POLICY = StopLossDefaultsPolicy()

DEFAULT_FRAUD_PATTERN_RISK_POLICY = FraudPatternRiskPolicy()
DEFAULT_FRAUD_RISK_TRACKER_POLICY = FraudRiskTrackerPolicy()
DEFAULT_ECONOMIC_RISK_ENVELOPE_POLICY = EconomicRiskEnvelopePolicy()
DEFAULT_PERFORMANCE_FEEDBACK_LEARNING_POLICY = PerformanceFeedbackLearningPolicy()
DEFAULT_CANONICAL_DECISION_BRIDGE_POLICY = CanonicalDecisionBridgePolicy()
DEFAULT_CAPABILITY_DIAGNOSTICS_POLICY = CapabilityDiagnosticsPolicy()
DEFAULT_PERFORMANCE_PROFILE_POLICY = PerformanceProfilePolicy()
