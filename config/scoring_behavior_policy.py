from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class GrowthStrategyScoringPolicy:
    effort_ease_by_level: Mapping[str, float] = field(
        default_factory=lambda: {"low": 0.9, "medium": 0.6, "high": 0.3}
    )
    risk_penalty_by_level: Mapping[str, float] = field(
        default_factory=lambda: {"low": 0.05, "medium": 0.18, "high": 0.35}
    )
    impact_by_signal: Mapping[str, float] = field(
        default_factory=lambda: {
            "x2": 0.95,
            "2x": 0.95,
            "double": 0.95,
            "удво": 0.95,
            "+50%": 0.85,
            "50%": 0.85,
            "полов": 0.85,
            "+20%": 0.70,
            "20%": 0.70,
            "+10%": 0.55,
            "10%": 0.55,
            "+5%": 0.40,
            "5%": 0.40,
        }
    )
    stage_impact_by_stage: Mapping[str, float] = field(
        default_factory=lambda: {
            "revenue": 0.70,
            "retention": 0.60,
            "activation": 0.55,
        }
    )
    default_impact: float = 0.50
    mechanism_length_threshold: int = 70
    evidence_keywords: tuple[str, ...] = ("data", "данн", "log", "event", "cohort", "retention", "attribution")
    experiment_keywords: tuple[str, ...] = ("a/b", "ab test", "holdout", "control")
    confidence_by_hint_count: Mapping[int, float] = field(
        default_factory=lambda: {3: 0.85, 2: 0.72, 1: 0.60, 0: 0.50}
    )
    default_ease: float = 0.5
    default_risk_penalty: float = 0.2


@dataclass(frozen=True)
class RetentionActivityPolicy:
    session_gap_ms: int = 20 * 60 * 1000
    rage_click_threshold_ms: int = 350
    short_window_days: int = 7
    long_window_days: int = 30
    day_ms: int = 86400 * 1000


@dataclass(frozen=True)
class ActionRankingPolicy:
    expected_profit_weight: float = 1.0
    ope_wis_weight: float = 1000.0
    uplift_weight: float = 100.0
    risk_penalty_weight: float = 1000.0


@dataclass(frozen=True)
class BidOptimizationPolicy:
    no_conversion_delta_pct: int = -10
    high_cpa_multiplier: float = 1.2
    high_cpa_delta_pct: int = -15
    low_cpa_multiplier: float = 0.8
    low_cpa_delta_pct: int = 10
    delta_floor_pct: int = -20
    delta_ceiling_pct: int = 20


@dataclass(frozen=True)
class BehavioralStatePolicy:
    anti_fatigue_weight: float = 0.65
    anti_trust_inverse_weight: float = 0.35


@dataclass(frozen=True)
class AdaptationMetricsPolicy:
    confidence_volume_saturation: int = 50
    weight_success_rate: float = 0.28
    weight_verification_rate: float = 0.24
    weight_roi_score: float = 0.24
    weight_latency_score: float = 0.12
    weight_stability_score: float = 0.12


@dataclass(frozen=True)
class PlannerMemoryPolicy:
    route_stability_same_route_floor: float = 0.45
    route_stability_same_route_bonus: float = 0.20
    route_stability_changed_route_multiplier: float = 0.55
    route_stability_changed_route_floor: float = 0.15
    route_stability_first_route_floor: float = 0.35
    route_stability_same_focus_mode_bonus: float = 0.08
    route_stability_no_route_multiplier: float = 0.45
    focus_mode_same_floor: float = 0.40
    focus_mode_same_bonus: float = 0.18
    focus_mode_changed_multiplier: float = 0.50
    focus_mode_changed_floor: float = 0.10
    focus_mode_first_floor: float = 0.30
    focus_mode_missing_multiplier: float = 0.50
    route_confidence_base: float = 0.4
    route_confidence_per_route_bonus: float = 0.2


@dataclass(frozen=True)
class AcquisitionFeasibilityPolicy:
    sustainability_partial_credit_with_customers: float = 0.5
    sustainability_partial_credit_without_customers: float = 0.0
    score_floor: float = 0.0
    score_ceiling: float = 1.0
    score_precision: int = 4


DEFAULT_GROWTH_STRATEGY_SCORING_POLICY = GrowthStrategyScoringPolicy()
DEFAULT_RETENTION_ACTIVITY_POLICY = RetentionActivityPolicy()
DEFAULT_ACTION_RANKING_POLICY = ActionRankingPolicy()

DEFAULT_BID_OPTIMIZATION_POLICY = BidOptimizationPolicy()
DEFAULT_BEHAVIORAL_STATE_POLICY = BehavioralStatePolicy()
DEFAULT_ADAPTATION_METRICS_POLICY = AdaptationMetricsPolicy()

DEFAULT_PLANNER_MEMORY_POLICY = PlannerMemoryPolicy()
DEFAULT_ACQUISITION_FEASIBILITY_POLICY = AcquisitionFeasibilityPolicy()
