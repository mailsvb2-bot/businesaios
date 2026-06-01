from __future__ import annotations

from core.experiments.guards.experiment_state_guard import ExperimentStateGuard
from core.experiments.guards.metric_membership_guard import MetricMembershipGuard
from core.experiments.guards.result_consistency_guard import ResultConsistencyGuard
from core.experiments.types import EvaluationSummary, VariantMetricSnapshot


def build_evaluation_summary(*, plan, result, unsafe_rollout_guard) -> EvaluationSummary:
    ExperimentStateGuard().ensure_reportable(plan)
    MetricMembershipGuard().ensure_defined(plan, result.primary_metric_key)
    ResultConsistencyGuard().ensure_matches_plan(plan, result)
    unsafe_rollout_guard.ensure_safe(
        decision=result.rollout_decision,
        risk_level=result.risk_level,
        significant=result.significant,
    )
    return EvaluationSummary(
        experiment_id=result.experiment_id,
        significant=result.significant,
        uplift=result.uplift,
        p_value=result.p_value,
        risk_level=result.risk_level,
        rollout_decision=result.rollout_decision,
        reasons=list(result.notes),
    )


def build_variant_metric_snapshot(*, variant_id: str, exposures: int, conversions: int, value: float) -> VariantMetricSnapshot:
    return VariantMetricSnapshot(
        variant_id=variant_id,
        exposures=exposures,
        conversions=conversions,
        value=value,
    )
