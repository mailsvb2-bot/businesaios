import pytest

from core.experiments.builders.experiment_plan_builder import ExperimentPlanBuilder
from core.experiments.enums import MetricDirection, VariantRole
from core.experiments.errors import MetricNotDefinedError
from core.experiments.repositories.assignment_repository import InMemoryAssignmentRepository
from core.experiments.repositories.experiment_repository import InMemoryExperimentRepository
from core.experiments.repositories.result_repository import InMemoryResultRepository
from core.experiments.service import ExperimentsService


def _service():
    return ExperimentsService(
        experiment_repository=InMemoryExperimentRepository(),
        assignment_repository=InMemoryAssignmentRepository(),
        result_repository=InMemoryResultRepository(),
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


def test_evaluate_from_snapshots_persists_prepared_result():
    service = _service()
    plan = service.register_experiment(_draft_plan())
    summary = service.evaluate_from_snapshots(
        experiment_id=plan.experiment_id,
        primary_metric_key="conversion_rate",
        control_exposures=200,
        control_conversions=20,
        treatment_exposures=200,
        treatment_conversions=35,
    )
    read_back = service.evaluate(experiment_id=plan.experiment_id, primary_metric_key="conversion_rate")
    assert read_back.experiment_id == summary.experiment_id
    assert read_back.uplift == summary.uplift


def test_evaluate_rejects_unknown_metric():
    service = _service()
    plan = service.register_experiment(_draft_plan())
    with pytest.raises(MetricNotDefinedError):
        service.evaluate_from_snapshots(
            experiment_id=plan.experiment_id,
            primary_metric_key="revenue_per_user",
            control_exposures=200,
            control_conversions=20,
            treatment_exposures=200,
            treatment_conversions=35,
        )
