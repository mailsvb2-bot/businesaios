from __future__ import annotations

from dataclasses import dataclass, field

from config.creative_model_defaults import (
    creative_attribution_credit_default,
    creative_expected_future_value_default,
    creative_fixed_cost_share_default,
    creative_market_fit_score_default,
)
from core.causal.types import CausalResult
from core.experiments.types import EvaluationSummary


@dataclass(frozen=True)
class CreativeEconomicsInput:
    creative_id: str
    segment_key: str
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    cogs: float
    variable_cost: float
    fixed_cost_share: float = field(default_factory=creative_fixed_cost_share_default)
    attribution_credit: float = field(default_factory=creative_attribution_credit_default)
    expected_future_value: float = field(default_factory=creative_expected_future_value_default)
    market_fit_score: float = field(default_factory=creative_market_fit_score_default)


@dataclass(frozen=True)
class CreativePnLSnapshot:
    creative_id: str
    attributed_revenue: float
    total_cost: float
    contribution_profit: float
    contribution_margin_ratio: float
    roi: float


@dataclass(frozen=True)
class IncrementalitySnapshot:
    creative_id: str
    estimated_effect: float
    confidence_score: float
    downside_risk: float
    method: str


@dataclass(frozen=True)
class ExperimentConfidenceSnapshot:
    creative_id: str
    uplift: float
    p_value: float
    confidence_score: float
    rollout_readiness: float


@dataclass(frozen=True)
class CreativeIntelligenceSnapshot:
    creative_id: str
    pnl: CreativePnLSnapshot
    incrementality: IncrementalitySnapshot
    experiment_confidence: ExperimentConfidenceSnapshot
    expected_value_score: float
    downside_envelope: float
    portfolio_rank_score: float
    explanations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortfolioBudgetAdvice:
    creative_id: str
    floor_budget: float
    target_budget: float
    ceiling_budget: float
    reallocation_bias: str


@dataclass(frozen=True)
class CreativeEvidenceBundle:
    causal_result: CausalResult | None = None
    experiment_summary: EvaluationSummary | None = None
