from __future__ import annotations

"""Experiment result evaluation and rollout policy."""

from config.experiments_policy import (
    DEFAULT_EXPERIMENT_RESULT_EVALUATION_POLICY,
    ExperimentResultEvaluationPolicy,
)
from core.experiments.evaluators.risk_evaluator import RiskEvaluator
from core.experiments.evaluators.significance_evaluator import SignificanceEvaluator
from core.experiments.evaluators.uplift_evaluator import UpliftEvaluator
from core.experiments.policies.rollout_policy import ConservativeRolloutPolicy
from core.experiments.types import EvaluationSummary


class ExperimentResultEvaluator:
    def __init__(
        self,
        uplift_evaluator: UpliftEvaluator | None = None,
        significance_evaluator: SignificanceEvaluator | None = None,
        risk_evaluator: RiskEvaluator | None = None,
        rollout_policy: ConservativeRolloutPolicy | None = None,
        evaluation_policy: ExperimentResultEvaluationPolicy = DEFAULT_EXPERIMENT_RESULT_EVALUATION_POLICY,
    ) -> None:
        self._uplift = uplift_evaluator or UpliftEvaluator()
        self._significance = significance_evaluator or SignificanceEvaluator()
        self._risk = risk_evaluator or RiskEvaluator()
        self._rollout_policy = rollout_policy or ConservativeRolloutPolicy()
        self._policy = evaluation_policy

    def evaluate(
        self,
        *,
        experiment_id: str,
        control_conversions: int,
        control_exposures: int,
        treatment_conversions: int,
        treatment_exposures: int,
        minimum_required_exposures: int,
    ) -> EvaluationSummary:
        uplift = self._uplift.evaluate(
            control_conversions=control_conversions,
            control_exposures=control_exposures,
            treatment_conversions=treatment_conversions,
            treatment_exposures=treatment_exposures,
        )
        p_value = self._significance.p_value_two_proportion(
            control_conversions=control_conversions,
            control_exposures=control_exposures,
            treatment_conversions=treatment_conversions,
            treatment_exposures=treatment_exposures,
        )
        significant = self._significance.is_significant(p_value)
        risk_level = self._risk.evaluate(
            uplift=uplift,
            p_value=p_value,
            minimum_required_exposures=minimum_required_exposures,
            control_exposures=control_exposures,
            treatment_exposures=treatment_exposures,
        )

        reasons: list[str] = []
        if control_exposures < minimum_required_exposures:
            reasons.append(self._policy.control_below_minimum_reason)
        if treatment_exposures < minimum_required_exposures:
            reasons.append(self._policy.treatment_below_minimum_reason)
        if uplift < self._policy.zero_uplift_floor:
            reasons.append(self._policy.negative_uplift_reason)
        if not significant:
            reasons.append(self._policy.not_significant_reason)

        rollout_decision = self._rollout_policy.evaluate(
            significant=significant,
            uplift=uplift,
            risk_level=risk_level,
        )
        return EvaluationSummary(
            experiment_id=experiment_id,
            significant=significant,
            uplift=uplift,
            p_value=p_value,
            risk_level=risk_level,
            rollout_decision=rollout_decision,
            reasons=reasons,
        )
