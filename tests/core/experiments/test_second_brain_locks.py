import pytest

from core.experiments.builders.experiment_plan_builder import ExperimentPlanBuilder
from core.experiments.enums import MetricDirection, RiskLevel, RolloutDecision, VariantRole
from core.experiments.errors import ResultConsistencyError
from core.experiments.repositories.assignment_repository import InMemoryAssignmentRepository
from core.experiments.repositories.experiment_repository import InMemoryExperimentRepository
from core.experiments.repositories.result_repository import InMemoryResultRepository
from core.experiments.service import ExperimentsService
from core.experiments.types import ExperimentResult, VariantMetricSnapshot


def _service(result_repository=None):
    return ExperimentsService(
        experiment_repository=InMemoryExperimentRepository(),
        assignment_repository=InMemoryAssignmentRepository(),
        result_repository=result_repository or InMemoryResultRepository(),
    )


def _draft_plan():
    builder = ExperimentPlanBuilder()
    return builder.build(
        name="Homepage CTA",
        hypothesis="New CTA improves conversion",
        subject_key="user",
        audience_key="all",
        owner="growth",
        variant_definitions=[
            ("control", VariantRole.CONTROL, 0.5),
            ("treatment", VariantRole.TREATMENT, 0.5),
        ],
        metric_definitions=[
            ("conversion_rate", MetricDirection.INCREASE, 0.01, False),
        ],
        minimum_sample_size=100,
        overlap_keys=["homepage"],
    )


def test_service_rejects_divergent_prepared_result():
    result_repository = InMemoryResultRepository()
    service = _service(result_repository=result_repository)
    plan = service.register_experiment(_draft_plan())
    bad = ExperimentResult(
        result_id="res_bad",
        experiment_id=plan.experiment_id,
        primary_metric_key="conversion_rate",
        control_variant_id="wrong_control",
        treatment_variant_id="wrong_treatment",
        control=VariantMetricSnapshot(variant_id="wrong_control", exposures=200, conversions=20, value=0.0),
        treatment=VariantMetricSnapshot(variant_id="wrong_treatment", exposures=200, conversions=30, value=0.0),
        uplift=0.5,
        p_value=0.01,
        significant=True,
        risk_level=RiskLevel.LOW,
        rollout_decision=RolloutDecision.FULL,
        notes=[],
    )
    result_repository.save(bad)
    with pytest.raises(ResultConsistencyError):
        service.evaluate(experiment_id=plan.experiment_id, primary_metric_key="conversion_rate")
