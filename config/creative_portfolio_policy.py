from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioScoringPolicy:
    expected_value_weight: float = 0.50
    rollout_readiness_weight: float = 0.25
    incrementality_confidence_weight: float = 0.20
    downside_penalty_weight: float = 0.35
    score_floor: float = -1.0
    score_ceiling: float = 1.0


@dataclass(frozen=True)
class CreativeStateBuilderPolicy:
    zero_value: float = 0.0


@dataclass(frozen=True)
class EconomicsStateBuilderPolicy:
    zero_value: float = 0.0


DEFAULT_PORTFOLIO_SCORING_POLICY = PortfolioScoringPolicy()
DEFAULT_CREATIVE_STATE_BUILDER_POLICY = CreativeStateBuilderPolicy()
DEFAULT_ECONOMICS_STATE_BUILDER_POLICY = EconomicsStateBuilderPolicy()
