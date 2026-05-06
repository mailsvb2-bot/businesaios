import pytest

from core.experiments.builders.experiment_plan_builder import ExperimentPlanBuilder
from core.experiments.enums import MetricDirection, VariantRole
from core.experiments.errors import ExperimentValidationError


def test_build_valid_plan():
    builder = ExperimentPlanBuilder()
    plan = builder.build(
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
        metadata={"team": "growth"},
    )
    assert plan.status.value == "draft"
    assert len(plan.variants) == 2
    assert len(plan.metrics) == 1


def test_build_rejects_invalid_variant_topology():
    builder = ExperimentPlanBuilder()
    with pytest.raises(ExperimentValidationError):
        builder.build(
            name="Broken",
            hypothesis="Broken",
            subject_key="user",
            audience_key="all",
            owner="growth",
            variant_definitions=[
                ("a", VariantRole.CONTROL, 0.34),
                ("b", VariantRole.TREATMENT, 0.33),
                ("c", VariantRole.TREATMENT, 0.33),
            ],
            metric_definitions=[
                ("conversion_rate", MetricDirection.INCREASE, 0.01, False),
            ],
            minimum_sample_size=100,
        )
