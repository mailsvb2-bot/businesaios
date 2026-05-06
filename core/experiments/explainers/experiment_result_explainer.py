from __future__ import annotations

from config.experiments_policy import (
    DEFAULT_EXPERIMENT_RESULT_EXPLANATION_POLICY,
    ExperimentResultExplanationPolicy,
)
from core.experiments.explainers.rollout_risk_explainer import RolloutRiskExplainer
from core.experiments.explainers.significance_explainer import SignificanceExplainer
from core.experiments.types import EvaluationSummary, ExperimentResult


class ExperimentResultExplainer:
    def __init__(
        self,
        significance_explainer: SignificanceExplainer | None = None,
        rollout_risk_explainer: RolloutRiskExplainer | None = None,
        explanation_policy: ExperimentResultExplanationPolicy = DEFAULT_EXPERIMENT_RESULT_EXPLANATION_POLICY,
    ) -> None:
        self._significance = significance_explainer or SignificanceExplainer()
        self._risk = rollout_risk_explainer or RolloutRiskExplainer()
        self._policy = explanation_policy

    def explain(self, summary: EvaluationSummary) -> str:
        significance_text = self._significance.explain(
            p_value=summary.p_value,
            significant=summary.significant,
        )
        risk_text = self._risk.explain(
            risk_level=summary.risk_level,
            decision=summary.rollout_decision,
        )
        reasons_text = (
            "; ".join(summary.reasons)
            if summary.reasons
            else self._policy.no_blocking_reasons_text
        )
        uplift_text = format(summary.uplift, f".{self._policy.uplift_precision_digits}f")
        return (
            f"experiment={summary.experiment_id}; "
            f"uplift={uplift_text}; "
            f"{significance_text}; "
            f"{risk_text}; "
            f"reasons={reasons_text}"
        )


def explain_experiment_result(
    result: ExperimentResult,
    *,
    explanation_policy: ExperimentResultExplanationPolicy = DEFAULT_EXPERIMENT_RESULT_EXPLANATION_POLICY,
) -> str:
    confidence = explanation_policy.confidence_ceiling - float(result.p_value)
    return (
        f"experiment_id={result.experiment_id}; uplift={result.uplift}; confidence={confidence}"
    )
