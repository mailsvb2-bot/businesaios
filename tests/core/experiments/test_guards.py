from dataclasses import replace

import pytest

from core.experiments.builders.experiment_plan_builder import ExperimentPlanBuilder
from core.experiments.enums import ExperimentStatus, MetricDirection, RiskLevel, RolloutDecision, VariantRole
from core.experiments.errors import ExperimentOverlapViolation, TrafficSufficiencyViolation, UnsafeRolloutViolation
from core.experiments.guards.experiment_overlap_guard import ExperimentOverlapGuard
from core.experiments.guards.traffic_sufficiency_guard import TrafficSufficiencyGuard
from core.experiments.guards.unsafe_rollout_guard import UnsafeRolloutGuard


def _plan(name: str, overlap_key: str):
    builder = ExperimentPlanBuilder()
    return builder.build(
        name=name,
        hypothesis="h",
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
        overlap_keys=[overlap_key],
    )


def test_overlap_guard_blocks_active_overlap():
    guard = ExperimentOverlapGuard()
    existing = replace(_plan("A", "homepage"), status=ExperimentStatus.ACTIVE)
    candidate = _plan("B", "homepage")
    with pytest.raises(ExperimentOverlapViolation):
        guard.ensure_no_overlap(candidate, [existing])


def test_traffic_guard_checks_both_branches():
    guard = TrafficSufficiencyGuard()
    with pytest.raises(TrafficSufficiencyViolation):
        guard.ensure_sufficient_traffic(control_exposures=10, treatment_exposures=100, minimum_required_exposures=50)


def test_unsafe_rollout_guard_blocks_full_without_significance():
    guard = UnsafeRolloutGuard()
    with pytest.raises(UnsafeRolloutViolation):
        guard.ensure_safe(decision=RolloutDecision.FULL, risk_level=RiskLevel.LOW, significant=False)
