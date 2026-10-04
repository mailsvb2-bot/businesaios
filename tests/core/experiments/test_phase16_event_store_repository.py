from __future__ import annotations

import pytest

from core.experiments.builders.experiment_plan_builder import ExperimentPlanBuilder
from core.experiments.enums import MetricDirection, VariantRole
from core.experiments.errors import ExperimentValidationError
from core.experiments.repositories.event_store_repository import EventStoreExperimentRepository
from runtime.boot.experiments_boot import build_experiments_service
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _plan(*, experiment_id: str = "exp_phase16", duration_days: int = 21):
    return ExperimentPlanBuilder().build(
        experiment_id=experiment_id,
        name="Phase 16 price test",
        hypothesis="A bounded offer change improves conversion",
        subject_key="customer",
        audience_key="eligible",
        owner="growth",
        variant_definitions=[
            ("control", VariantRole.CONTROL, 0.5),
            ("treatment", VariantRole.TREATMENT, 0.5),
        ],
        metric_definitions=[
            ("conversion_rate", MetricDirection.INCREASE, 0.01, False),
            ("complaint_rate", MetricDirection.DECREASE, 0.0, True),
        ],
        minimum_sample_size=100,
        duration_days=duration_days,
        overlap_keys=["offer:main"],
    )


def _service(store, *, tenant_id="tenant-1", business_id="business-1"):
    return build_experiments_service(
        event_store=store,
        tenant_id=tenant_id,
        business_id=business_id,
    )


def test_phase16_plan_covers_required_duration_and_rejects_invalid_duration():
    plan = _plan(duration_days=30)
    assert plan.duration_days == 30
    with pytest.raises(ExperimentValidationError, match="duration_days"):
        _plan(experiment_id="exp_bad_duration", duration_days=0)


def test_event_store_experiment_survives_service_reconstruction():
    store = MemoryEventStore()
    active = _service(store).register_experiment(_plan())

    restored = EventStoreExperimentRepository(
        store,
        tenant_id="tenant-1",
        business_id="business-1",
    ).get(active.experiment_id)

    assert restored == active
    assert restored is not None
    assert restored.status.value == "active"
    assert restored.duration_days == 21


def test_event_store_experiment_is_tenant_and_business_isolated():
    store = MemoryEventStore()
    active = _service(store).register_experiment(_plan())

    assert EventStoreExperimentRepository(
        store,
        tenant_id="tenant-2",
        business_id="business-1",
    ).get(active.experiment_id) is None
    assert EventStoreExperimentRepository(
        store,
        tenant_id="tenant-1",
        business_id="business-2",
    ).get(active.experiment_id) is None


def test_assignment_is_idempotent_across_service_reconstruction():
    store = MemoryEventStore()
    service = _service(store)
    active = service.register_experiment(_plan())
    first = service.assign_subject(
        experiment_id=active.experiment_id,
        subject_id="customer-1",
        correlation_id="corr-1",
        assigned_at="2026-10-04T10:00:00Z",
    )

    restarted = _service(store)
    second = restarted.assign_subject(
        experiment_id=active.experiment_id,
        subject_id="customer-1",
        correlation_id="corr-retry",
        assigned_at="2026-10-04T10:05:00Z",
    )

    assert second == first


def test_result_and_experiment_decision_survive_service_reconstruction():
    store = MemoryEventStore()
    service = _service(store)
    active = service.register_experiment(_plan())
    summary = service.evaluate_from_snapshots(
        experiment_id=active.experiment_id,
        primary_metric_key="conversion_rate",
        control_exposures=300,
        control_conversions=30,
        treatment_exposures=300,
        treatment_conversions=60,
    )

    restarted = _service(store)
    restored = restarted.evaluate(active.experiment_id, "conversion_rate")
    persisted_plan = EventStoreExperimentRepository(
        store,
        tenant_id="tenant-1",
        business_id="business-1",
    ).get(active.experiment_id)

    assert restored == summary
    assert persisted_plan is not None
    assert persisted_plan.status.value == "evaluated"


def test_authorized_experiment_identity_cannot_be_rewritten():
    store = MemoryEventStore()
    repo = EventStoreExperimentRepository(
        store,
        tenant_id="tenant-1",
        business_id="business-1",
    )
    service = _service(store)
    active = service.register_experiment(_plan())
    changed = ExperimentPlanBuilder().build(
        experiment_id=active.experiment_id,
        name=active.name,
        hypothesis="silently changed after authorization",
        subject_key=active.subject_key,
        audience_key=active.audience_key,
        owner=active.owner,
        variant_definitions=[
            ("control", VariantRole.CONTROL, 0.5),
            ("treatment", VariantRole.TREATMENT, 0.5),
        ],
        metric_definitions=[
            ("conversion_rate", MetricDirection.INCREASE, 0.01, False),
        ],
        minimum_sample_size=100,
        duration_days=active.duration_days,
        overlap_keys=list(active.overlap_keys),
    )

    with pytest.raises(ValueError, match="identity collision"):
        repo.save(changed)
