from __future__ import annotations

from config.strategic_growth_policy import DEFAULT_EXPERIMENTS_SERVICE_POLICY, ExperimentsServicePolicy
from core.experiments.builders.service_support import build_evaluation_summary, build_variant_metric_snapshot
from core.experiments.builders.variant_selection_builder import VariantSelectionBuilder
from core.experiments.enums import RiskLevel, RolloutDecision, VariantRole
from core.experiments.evaluators.experiment_result_evaluator import ExperimentResultEvaluator
from core.experiments.guard import ExperimentsGuard
from core.experiments.guards.assignment_input_guard import AssignmentInputGuard
from core.experiments.guards.experiment_state_guard import ExperimentStateGuard
from core.experiments.guards.metric_membership_guard import MetricMembershipGuard
from core.experiments.guards.plan_guard import ExperimentPlanGuard
from core.experiments.guards.result_consistency_guard import ResultConsistencyGuard
from core.experiments.guards.snapshot_input_guard import SnapshotInputGuard
from core.experiments.readers.experiment_reader import ExperimentReader
from core.experiments.readers.result_reader import ResultReader
from core.experiments.types import (
    EvaluationSummary,
    Experiment,
    ExperimentPlan,
    ExperimentResult,
    VariantMetricSnapshot,
)
from core.experiments.writers.assignment_writer import AssignmentWriter
from core.experiments.writers.experiment_writer import ExperimentWriter
from core.experiments.writers.result_writer import ResultWriter


class ExperimentsService:
    def __init__(
        self,
        *,
        experiment_repository,
        assignment_repository,
        result_repository,
        guard: ExperimentsGuard | None = None,
        plan_guard: ExperimentPlanGuard | None = None,
        assignment_input_guard: AssignmentInputGuard | None = None,
        snapshot_input_guard: SnapshotInputGuard | None = None,
        experiment_state_guard: ExperimentStateGuard | None = None,
        metric_membership_guard: MetricMembershipGuard | None = None,
        result_consistency_guard: ResultConsistencyGuard | None = None,
        variant_selection_builder: VariantSelectionBuilder | None = None,
        result_evaluator: ExperimentResultEvaluator | None = None,
        policy: ExperimentsServicePolicy | None = None,
    ) -> None:
        self._experiment_repository = experiment_repository
        self._assignment_repository = assignment_repository
        self._result_repository = result_repository
        self._reader = ExperimentReader(experiment_repository)
        self._result_reader = ResultReader(result_repository)
        self._experiment_writer = ExperimentWriter(experiment_repository)
        self._assignment_writer = AssignmentWriter(assignment_repository)
        self._result_writer = ResultWriter(result_repository)
        self._guard = guard or ExperimentsGuard()
        self._plan_guard = plan_guard or ExperimentPlanGuard()
        self._assignment_input_guard = assignment_input_guard or AssignmentInputGuard()
        self._snapshot_input_guard = snapshot_input_guard or SnapshotInputGuard()
        self._experiment_state_guard = experiment_state_guard or ExperimentStateGuard()
        self._metric_membership_guard = metric_membership_guard or MetricMembershipGuard()
        self._result_consistency_guard = result_consistency_guard or ResultConsistencyGuard()
        self._variant_selection_builder = variant_selection_builder or VariantSelectionBuilder()
        self._result_evaluator = result_evaluator or ExperimentResultEvaluator()
        self._policy = policy or DEFAULT_EXPERIMENTS_SERVICE_POLICY

    def register_experiment(self, plan: ExperimentPlan) -> ExperimentPlan:
        self._plan_guard.validate_for_registration(plan)
        self._guard.overlap_guard.ensure_no_overlap(
            candidate_plan=plan,
            existing_plans=self._experiment_repository.list_all(),
        )
        return self._experiment_writer.activate(plan)

    def assign_subject(self, experiment_id: str, subject_id: str, correlation_id: str, assigned_at: str):
        self._assignment_input_guard.validate(
            subject_id=subject_id,
            correlation_id=correlation_id,
            assigned_at=assigned_at,
        )
        plan = self._reader.get(experiment_id)
        self._experiment_state_guard.ensure_assignable(plan)
        existing = self._assignment_repository.find_by_subject(experiment_id, subject_id)
        if existing is not None:
            return existing
        selected_variant = self._variant_selection_builder.build(plan, subject_id)
        return self._assignment_writer.save(
            experiment_id=experiment_id,
            subject_id=subject_id,
            variant_id=selected_variant.variant_id,
            assigned_at=assigned_at,
            correlation_id=correlation_id,
        )

    def evaluate(self, experiment_id: str, primary_metric_key: str) -> EvaluationSummary:
        plan = self._reader.get(experiment_id)
        result = self._result_reader.get_latest_by_metric(experiment_id, primary_metric_key)
        return build_evaluation_summary(
            plan=plan,
            result=result,
            unsafe_rollout_guard=self._guard.unsafe_rollout_guard,
        )

    def evaluate_from_snapshots(
        self,
        *,
        experiment_id: str,
        primary_metric_key: str,
        control_exposures: int,
        control_conversions: int,
        treatment_exposures: int,
        treatment_conversions: int,
        control_value: float | None = None,
        treatment_value: float | None = None,
    ) -> EvaluationSummary:
        control_value = self._policy.zero_metric_value if control_value is None else float(control_value)
        treatment_value = self._policy.zero_metric_value if treatment_value is None else float(treatment_value)
        self._snapshot_input_guard.validate(
            primary_metric_key=primary_metric_key,
            control_exposures=control_exposures,
            control_conversions=control_conversions,
            treatment_exposures=treatment_exposures,
            treatment_conversions=treatment_conversions,
            control_value=control_value,
            treatment_value=treatment_value,
        )
        plan = self._reader.get(experiment_id)
        self._experiment_state_guard.ensure_snapshot_evaluable(plan)
        self._metric_membership_guard.ensure_defined(plan, primary_metric_key)
        self._guard.traffic_guard.ensure_sufficient_traffic(
            control_exposures=control_exposures,
            treatment_exposures=treatment_exposures,
            minimum_required_exposures=plan.minimum_sample_size,
        )
        summary = self._result_evaluator.evaluate(
            experiment_id=experiment_id,
            control_conversions=control_conversions,
            control_exposures=control_exposures,
            treatment_conversions=treatment_conversions,
            treatment_exposures=treatment_exposures,
            minimum_required_exposures=plan.minimum_sample_size,
        )
        self._guard.unsafe_rollout_guard.ensure_safe(
            decision=summary.rollout_decision,
            risk_level=summary.risk_level,
            significant=summary.significant,
        )
        control_variant = self._get_variant_by_role(plan, VariantRole.CONTROL)
        treatment_variant = self._get_variant_by_role(plan, VariantRole.TREATMENT)
        result = self._result_writer.save(
            experiment_id=experiment_id,
            primary_metric_key=primary_metric_key,
            control_variant_id=control_variant.variant_id,
            treatment_variant_id=treatment_variant.variant_id,
            control=build_variant_metric_snapshot(
                variant_id=control_variant.variant_id,
                exposures=control_exposures,
                conversions=control_conversions,
                value=control_value,
            ),
            treatment=build_variant_metric_snapshot(
                variant_id=treatment_variant.variant_id,
                exposures=treatment_exposures,
                conversions=treatment_conversions,
                value=treatment_value,
            ),
            uplift=summary.uplift,
            p_value=summary.p_value,
            significant=summary.significant,
            risk_level=summary.risk_level,
            rollout_decision=summary.rollout_decision,
            notes=list(summary.reasons),
        )
        self._result_consistency_guard.ensure_matches_plan(plan, result)
        self._experiment_writer.mark_evaluated(plan)
        return summary

    def _get_variant_by_role(self, plan: ExperimentPlan, role: VariantRole):
        for variant in plan.variants:
            if variant.role == role:
                return variant
        raise RuntimeError(f"variant with role '{role.value}' not found")


# backward-compatible legacy function surface

def build_empty_result(
    experiment: Experiment,
    *,
    policy: ExperimentsServicePolicy | None = None,
) -> ExperimentResult:
    service_policy = policy or DEFAULT_EXPERIMENTS_SERVICE_POLICY
    snapshot = VariantMetricSnapshot(variant_id="legacy", exposures=0, conversions=0, value=service_policy.legacy_snapshot_value)
    return ExperimentResult(
        result_id="res_legacy_empty",
        experiment_id=experiment.experiment_id,
        primary_metric_key="legacy_metric",
        control_variant_id="legacy_control",
        treatment_variant_id="legacy_treatment",
        control=snapshot,
        treatment=snapshot,
        uplift=service_policy.legacy_uplift,
        p_value=service_policy.legacy_p_value,
        significant=False,
        risk_level=RiskLevel.MEDIUM,
        rollout_decision=RolloutDecision.HOLD,
        notes=["legacy empty result"],
    )
