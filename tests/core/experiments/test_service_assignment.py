from core.experiments.builders.experiment_plan_builder import ExperimentPlanBuilder
from core.experiments.enums import MetricDirection, VariantRole
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


def test_assignment_is_deterministic_and_idempotent():
    service = _service()
    plan = service.register_experiment(_draft_plan())
    first = service.assign_subject(
        experiment_id=plan.experiment_id,
        subject_id="user-1",
        correlation_id="corr-1",
        assigned_at="2026-03-08T10:00:00Z",
    )
    second = service.assign_subject(
        experiment_id=plan.experiment_id,
        subject_id="user-1",
        correlation_id="corr-2",
        assigned_at="2026-03-08T10:01:00Z",
    )
    assert first.assignment_id == second.assignment_id
    assert first.variant_id == second.variant_id
