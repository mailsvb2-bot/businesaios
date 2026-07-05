from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LearningSystemPolicy:
    default_collapse_threshold: float = -1.0
    default_ltv_collapse_threshold: float = 0.0
    default_ltv_drop_pct: float = 0.2
    default_min_samples: int = 10
    default_rollout_pct: int = 10
    world_state_schema_version: int = 1
    zero_value: float = 0.0
    unit_value: float = 1.0
    world_state_timestamp_multiplier: int = 1000
    system_role: str = "system"
    workspace_product_name: str = "BusinesAIOS Workspace"
    system_user_id: str = "system"
    safe_mode_default: bool = False


@dataclass(frozen=True)
class StrategicHorizonDecisionPolicy:
    financial_risk_defense_threshold: float = 0.8
    policy_divergence_defense_threshold: float = 0.7
    churn_unstable_threshold: float = 0.15
    margin_expand_threshold: float = 0.25
    growth_expand_threshold: float = 0.05
    offline_score_expand_threshold: float = 0.7
    financial_risk_expand_ceiling: float = 0.4
    margin_optimize_threshold: float = 0.18
    online_reward_confidence_optimize_threshold: float = 0.5
    financial_risk_optimize_ceiling: float = 0.6
    horizon_days_defense: int = 7
    horizon_days_stabilize: int = 14
    horizon_days_optimize: int = 30
    horizon_days_expand: int = 45
    horizon_days_research: int = 21
    defense_budget_multiplier: float = 0.2
    stabilize_budget_multiplier: float = 0.4
    optimize_budget_multiplier: float = 0.6
    expand_budget_multiplier: float = 0.9
    research_budget_multiplier: float = 0.5
    budget_baseline: float = 1.0
    zero_value: float = 0.0
    one_value: float = 1.0
    growth_pressure_defense: float = 0.1
    growth_rate_weight: float = 0.5
    margin_weight: float = 0.3
    churn_inverse_weight: float = 0.2
    expand_signal_multiplier: float = 1.5
    frozen_offline_score_ceiling: float = 0.5
    aggressive_online_confidence_threshold: float = 0.7


@dataclass(frozen=True)
class BehaviorTelemetryPolicy:
    default_tenant_id: str = "default"
    default_limit: int = 200
    default_lookback_days: int = 30
    milliseconds_per_second: int = 1000
    seconds_per_day: int = 24 * 3600
    mixed_event_limit: int = 200
    engagement_zero: float = 0.0
    org_context_anti: float = 0.0
    org_context_purchase_probability: float = 0.0
    org_context_hesitation_score: float = 0.0
    target_norm: int = 1
    zero_seconds_window_ms: int = 10_000
    behavior_schema: str = "behavior_telemetry@v1"
    callback_kind: str = "callback"
    message_kind: str = "message"
    default_button_id: str = ""
    default_org: dict[str, object] = field(default_factory=dict)
    wanted_event_types: tuple[str, ...] = (
        "behavior_telemetry",
        "ui_click",
        "offer_shown",
        "offer_clicked",
        "paywall_opened",
        "purchase_attempt",
        "purchase_success",
        "purchase_failed",
        "payment_success",
        "payment_failed",
        "audio_started",
        "audio_progress",
        "audio_completed",
        "audio_stopped",
    )


@dataclass(frozen=True)
class AnthropicProviderPolicy:
    default_version: str = "2023-06-01"
    default_timeout_s: int = 20
    default_max_tokens: int = 600
    default_temperature: float = 0.2
    content_preview_limit: int = 8000
    default_stop_reason: str = "stop"
    default_user_role: str = "user"
    empty_content: str = ""
    messages_path_suffix: str = "/v1/messages"


@dataclass(frozen=True)
class KnowledgeDeduplicationPolicy:
    duplicate_threshold: float = 0.90


@dataclass(frozen=True)
class OperatorCatalogPolicy:
    default_phase_gain: float = 0.25
    default_k_tp: float = 0.08
    default_k_vp: float = 0.06
    default_k_it: float = 0.04
    default_anti_drain: float = 0.15
    phase_gain_min: float = 0.0
    phase_gain_max: float = 0.5
    coupling_min: float = 0.0
    coupling_max: float = 0.20
    anti_drain_min: float = 0.0
    anti_drain_max: float = 0.35
    scale_min: float = 0.25
    scale_max: float = 3.0
    default_scale: float = 1.0


@dataclass(frozen=True)
class StrategicFinanceTypePolicy:
    zero_money: Decimal = Decimal('0')
    one_multiplier: Decimal = Decimal('1')
    default_probability: Decimal = Decimal('0.5')


@dataclass(frozen=True)
class CausalBuilderPolicy:
    event_page_limit: int = 5000
    binary_dataset_max_events: int = 50_000
    diff_in_diff_max_events: int = 100_000
    milliseconds_per_second: int = 1000
    seconds_per_day: int = 24 * 3600
    default_lookback_days: int = 30
    zero_timestamp: int = 0
    unit_treated_value: float = 1.0
    unit_control_value: float = 0.0
    default_outcome_value: float = 0.0
    pre_period_label: str = "pre"
    post_period_label: str = "post"
    pagination_step_ms: int = 1


@dataclass(frozen=True)
class DoublyRobustPolicy:
    default_smoothing: float = 0.0
    default_clip_min: float = 0.05
    default_clip_max: float = 0.95
    default_categorical_limit: int = 32
    default_method: str = "dr_strata_ols_v1"
    propensity_fallback: float = 0.5
    treatment_threshold: float = 0.5
    control_value: float = 0.0
    treated_value: float = 1.0
    default_notes: str = "AIPW doubly-robust with stratified propensity + OLS outcome regression."
    zero_features: int = 0


DEFAULT_LEARNING_SYSTEM_POLICY = LearningSystemPolicy()
DEFAULT_STRATEGIC_HORIZON_DECISION_POLICY = StrategicHorizonDecisionPolicy()
DEFAULT_BEHAVIOR_TELEMETRY_POLICY = BehaviorTelemetryPolicy()
DEFAULT_ANTHROPIC_PROVIDER_POLICY = AnthropicProviderPolicy()
DEFAULT_KNOWLEDGE_DEDUPLICATION_POLICY = KnowledgeDeduplicationPolicy()
DEFAULT_OPERATOR_CATALOG_POLICY = OperatorCatalogPolicy()
DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY = StrategicFinanceTypePolicy()
DEFAULT_CAUSAL_BUILDER_POLICY = CausalBuilderPolicy()
DEFAULT_DOUBLY_ROBUST_POLICY = DoublyRobustPolicy()
