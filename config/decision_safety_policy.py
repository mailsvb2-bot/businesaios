from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AutoDeployerPolicy:
    shadow_threshold: float = 0.2


@dataclass(frozen=True)
class PolicySelectorPolicy:
    default_canary_pct: float = 0.0
    default_min_decisions: int = 0
    default_max_error_rate: float = 1.0
    default_auto_promote: bool = False
    rollout_pct_floor: int = 0
    rollout_pct_ceiling: int = 100
    rollout_pct_divisor: float = 100.0


@dataclass(frozen=True)
class DecisionValidatorPolicy:
    zero_budget_delta: float = 0.0
    zero_risk_score: float = 0.0
    risk_score_ceiling: float = 1.0
    zero_rank_score: float = 0.0
    route_lead_action_type: str = "route_lead"


@dataclass(frozen=True)
class RewardGuardPolicyDefaults:
    min_reward: float = -0.25
    min_margin: float = 0.0
    zero_value: float = 0.0
    expected_reward_key: str = "expected_reward"
    expected_margin_key: str = "expected_margin"
    blocked_reason: str = "reward_guard_blocked"
    ok_reason: str = "reward_guard_ok"


@dataclass(frozen=True)
class RiskScorerPolicy:
    zero_value: float = 0.0
    amount_threshold: float = 500.0
    amount_risk_increment: float = 0.45
    audience_size_threshold: int = 100
    audience_risk_increment: float = 0.35
    review_flag_risk_increment: float = 0.25
    score_ceiling: float = 1.0
    high_financial_amount_reason: str = "high_financial_amount"
    large_audience_reason: str = "large_audience"
    explicit_review_flag_reason: str = "explicit_review_flag"


@dataclass(frozen=True)
class RiskScoreGuardPolicy:
    block_threshold: float = 0.8
    review_threshold: float = 0.5
    blocked_reason: str = "risk_score_blocked"
    review_reason: str = "risk_score_review"
    ok_reason: str = "risk_score_ok"


@dataclass(frozen=True)
class SafetyProfilePolicy:
    negative_amount_floor: float = 0.0
    default_blast_radius_financial_amount: float = 1000.0
    default_blast_radius_users_affected: int = 500
    default_blast_radius_records_affected: int = 1000
    default_blast_radius_services_touched: int = 2
    capture_payment_financial_amount: float = 100.0
    capture_payment_users_affected: int = 1
    capture_payment_records_affected: int = 10
    capture_payment_services_touched: int = 1
    marketing_offer_financial_amount: float = 500.0
    marketing_offer_users_affected: int = 250
    marketing_offer_records_affected: int = 250
    marketing_offer_services_touched: int = 1
    circuit_breaker_max_consecutive_failures: int = 3
    action_budget_max_cost: float = 5000.0
    action_budget_max_actions: int = 1000
    approval_min_approvals: int = 2
    simulation_gate_min_score: float = 0.70
    runaway_loop_repetition_threshold: int = 3
    capture_payment_prefix: str = "capture_payment"
    marketing_offer_prefix: str = "send_marketing_offer"
    default_approval_prefixes: tuple[str, ...] = field(default_factory=tuple)
    simulation_gate_prefixes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CapabilityBootstrapPolicy:
    bootstrap_health_floor: float = 0.72
    bootstrap_confidence_floor: float = 0.55
    bootstrap_routing_state: str = "enabled"
    bootstrap_recommended_autonomy_tier: str = "bounded_autonomy"
    bootstrap_mode: str = "first_run_enabled_without_verified_evidence"


@dataclass(frozen=True)
class CapabilityFallbackPolicy:
    low_health_operator_handoff_threshold: float = 0.35
    full_autonomy_tier: str = "full_autonomy"
    stale_state: str = "stale"
    fallback_preferred_state: str = "fallback_preferred"
    notify_owner_action_type: str = "notify_owner"
    degraded_execution_kind: str = "degraded_execution"
    operator_handoff_kind: str = "operator_handoff"
    communications_capability_key: str = "communications_write"
    protected_capability_keys: tuple[str, ...] = ("ads_write", "budget_change", "platform_listing_write", "profile_publish")
    internal_execution_capability_key: str = "internal_execution"


@dataclass(frozen=True)
class CapabilityRoutingPolicy:
    maturity_score_real: float = 1.0
    maturity_score_shell: float = 0.55
    maturity_score_placeholder: float = 0.10
    maturity_score_default: float = 0.25
    weight_health: float = 0.28
    weight_proofability: float = 0.28
    weight_latency: float = 0.14
    weight_cost: float = 0.14
    weight_maturity: float = 0.08
    continuity_bonus_cap: float = 0.12
    unhealthy_health_cap: float = 0.34


@dataclass(frozen=True)
class GoalEvaluationPolicy:
    explicit_goal_reached_weight: float = 0.60
    verified_weight: float = 0.25
    verification_confidence_weight: float = 0.15
    verification_confidence_goal_achieved_threshold: float = 0.70
    repeated_failure_terminal_threshold: int = 2
    achieved_confidence_floor: float = 0.85


@dataclass(frozen=True)
class AutonomyAdvisoryPolicy:
    scale_expected_value_threshold: float = 0.35
    scale_downside_ceiling: float = 0.30
    launch_expected_value_threshold: float = 0.15
    launch_rollout_readiness_threshold: float = 0.45
    stop_expected_value_threshold: float = -0.05
    stop_downside_threshold: float = 0.70
    select_confidence_threshold: float = 0.25
    architecture_stability_low_threshold: float = 0.45
    flow_turbulence_high_threshold: float = 0.60
    competitive_shift_high_threshold: float = 0.70


@dataclass(frozen=True)
class GoalDecompositionPolicy:
    retention_keywords: tuple[str, ...] = ("retention", "reactivation", "repeat", "churn")
    reputation_keywords: tuple[str, ...] = ("review", "reputation", "ugc", "rating")
    demand_generation_keywords: tuple[str, ...] = ("lead", "demand", "pipeline", "appointment")
    revenue_growth_keywords: tuple[str, ...] = ("revenue", "sales", "profit", "monetiz", "conversion")
    default_priority_weight: float = 1.0
    activation_priority_weight: float = 1.1
    verification_priority_weight: float = 1.2
    scale_priority_weight: float = 0.9


DEFAULT_AUTO_DEPLOYER_POLICY = AutoDeployerPolicy()
DEFAULT_POLICY_SELECTOR_POLICY = PolicySelectorPolicy()
DEFAULT_DECISION_VALIDATOR_POLICY = DecisionValidatorPolicy()
DEFAULT_REWARD_GUARD_POLICY_DEFAULTS = RewardGuardPolicyDefaults()
DEFAULT_RISK_SCORER_POLICY = RiskScorerPolicy()
DEFAULT_RISK_SCORE_GUARD_POLICY = RiskScoreGuardPolicy()
DEFAULT_SAFETY_PROFILE_POLICY = SafetyProfilePolicy()

DEFAULT_CAPABILITY_BOOTSTRAP_POLICY = CapabilityBootstrapPolicy()
DEFAULT_CAPABILITY_FALLBACK_POLICY = CapabilityFallbackPolicy()
DEFAULT_CAPABILITY_ROUTING_POLICY = CapabilityRoutingPolicy()
DEFAULT_GOAL_EVALUATION_POLICY = GoalEvaluationPolicy()
DEFAULT_AUTONOMY_ADVISORY_POLICY = AutonomyAdvisoryPolicy()
DEFAULT_GOAL_DECOMPOSITION_POLICY = GoalDecompositionPolicy()
