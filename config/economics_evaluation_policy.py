from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class EconomicsEvaluationScorePolicy:
    zero_score: float = 0.0


@dataclass(frozen=True)
class MarginBuilderPolicy:
    zero_ratio: float = 0.0
    weak_net_margin_threshold: float = 0.05
    stable_net_margin_threshold: float = 0.20


@dataclass(frozen=True)
class UnitEconomicsBuilderPolicy:
    minimum_period_days: int = 1
    minimum_active_customers: int = 0
    zero_ratio: float = 0.0


@dataclass(frozen=True)
class LTVCACEvaluatorPolicy:
    healthy_ratio_threshold: float = 3.0
    warning_ratio_threshold: float = 1.5


DEFAULT_ECONOMICS_EVALUATION_SCORE_POLICY = EconomicsEvaluationScorePolicy()
DEFAULT_MARGIN_BUILDER_POLICY = MarginBuilderPolicy()
DEFAULT_UNIT_ECONOMICS_BUILDER_POLICY = UnitEconomicsBuilderPolicy()
DEFAULT_LTV_CAC_EVALUATOR_POLICY = LTVCACEvaluatorPolicy()
