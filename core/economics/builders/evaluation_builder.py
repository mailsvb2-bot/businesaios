from __future__ import annotations

from dataclasses import dataclass, field

from config.economics_evaluation_policy import (
    DEFAULT_ECONOMICS_EVALUATION_SCORE_POLICY,
    EconomicsEvaluationScorePolicy,
)

from ..evaluators.budget_pressure_evaluator import BudgetPressureEvaluator
from ..evaluators.ltv_cac_evaluator import LTVCACEvaluator
from ..evaluators.margin_health_evaluator import MarginHealthEvaluator
from ..evaluators.payback_risk_evaluator import PaybackRiskEvaluator
from ..types import BudgetEnvelope, CACSnapshot, EconomicsEvaluation, LTVSnapshot, MarginSnapshot, PaybackSnapshot


@dataclass
class EconomicsEvaluationBuilder:
    budget_pressure_evaluator: BudgetPressureEvaluator = field(default_factory=BudgetPressureEvaluator)
    margin_health_evaluator: MarginHealthEvaluator = field(default_factory=MarginHealthEvaluator)
    ltv_cac_evaluator: LTVCACEvaluator = field(default_factory=LTVCACEvaluator)
    payback_risk_evaluator: PaybackRiskEvaluator = field(default_factory=PaybackRiskEvaluator)
    score_policy: EconomicsEvaluationScorePolicy = field(default_factory=lambda: DEFAULT_ECONOMICS_EVALUATION_SCORE_POLICY)

    def build(self, *, budget: BudgetEnvelope, margin: MarginSnapshot, ltv: LTVSnapshot, cac: CACSnapshot, payback: PaybackSnapshot) -> EconomicsEvaluation:
        return EconomicsEvaluation(
            budget_pressure_status=self.budget_pressure_evaluator.evaluate(budget),
            margin_health_status=self.margin_health_evaluator.evaluate(margin),
            ltv_cac_status=self.ltv_cac_evaluator.evaluate(ltv, cac),
            payback_risk_status=self.payback_risk_evaluator.evaluate(payback),
            scores=self._build_scores(budget=budget, margin=margin, ltv=ltv, cac=cac, payback=payback),
        )

    def _build_scores(self, *, budget: BudgetEnvelope, margin: MarginSnapshot, ltv: LTVSnapshot, cac: CACSnapshot, payback: PaybackSnapshot) -> dict[str, float]:
        zero_score = self.score_policy.zero_score
        ltv_cac_ratio = (
            ltv.ltv / cac.blended_cac
            if ltv.ltv is not None and cac.blended_cac not in (None, zero_score)
            else zero_score
        )
        return {
            'ltv_cac_ratio': ltv_cac_ratio,
            'net_margin_ratio': margin.net_margin_ratio,
            'gross_margin_ratio': margin.gross_margin_ratio,
            'recommended_spend_cap': budget.recommended_spend_cap,
            'payback_days': payback.cac_payback_days or zero_score,
        }
