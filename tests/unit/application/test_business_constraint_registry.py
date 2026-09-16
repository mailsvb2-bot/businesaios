from __future__ import annotations

import pytest

from application.business_constraint import (
    BusinessConstraintHistoryInvariantViolation,
    BusinessConstraintProjector,
    BusinessConstraintRegistry,
)
from contracts.business_constraints import (
    BusinessConstraint,
    BusinessConstraintNotFound,
    ConstraintLifecycleStatus,
    ConstraintSeverity,
)
from contracts.event_store import BusinessFactV1
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)


def _registry():
    events = MemoryEventStore()
    return BusinessConstraintRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_constraint_lifecycle_is_idempotent_and_subject_is_stable() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="create",
        constraint_kind="budget_guard", severity="hard", subject_type="campaign", subject_id="campaign-1",
        state_key="enforced", occurred_at_ms=100,
    )
    assert created.severity is ConstraintSeverity.HARD
    count = len(events.events)
    assert registry.create(
        tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="create",
        constraint_kind="budget_guard", severity="hard", subject_type="campaign", subject_id="campaign-1",
        state_key="enforced", occurred_at_ms=999,
    ) == created
    assert len(events.events) == count
    updated = registry.update(
        tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="update",
        severity="soft", state_key="warning", occurred_at_ms=200,
    )
    assert updated.severity is ConstraintSeverity.SOFT
    assert updated.state_key == "warning"
    archived = registry.archive(
        tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="archive",
        occurred_at_ms=300,
    )
    assert archived.lifecycle_status is ConstraintLifecycleStatus.ARCHIVED
    with pytest.raises(ValueError, match="archived business constraint"):
        registry.update(
            tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="late",
            state_key="enforced", occurred_at_ms=400,
        )


def test_constraint_contract_requires_complete_subject_relation() -> None:
    with pytest.raises(ValueError, match="provided together"):
        BusinessConstraint(
            constraint_id="c", tenant_id="t", business_id="b", constraint_kind="approval",
            subject_type="order", subject_id=None,
        )
    with pytest.raises(ValueError, match="unsupported business constraint schema_version"):
        BusinessConstraint(
            constraint_id="c", tenant_id="t", business_id="b", constraint_kind="approval", schema_version=2,
        )


def test_constraint_projection_rejects_rewritten_subject_and_schema() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="create", tenant_id="t", business_id="b", fact_type="constraint.created", entity_id="c",
        event_time_ms=100, observed_at_ms=100, source="business_constraint_registry",
        payload={
            "schema_version": 1, "constraint_kind": "approval", "severity": "hard",
            "subject_type": "order", "subject_id": "o1", "state_key": "required",
        },
    ).as_event())
    events.append_event(BusinessFactV1(
        fact_id="rewrite", tenant_id="t", business_id="b", fact_type="constraint.updated", entity_id="c",
        event_time_ms=200, observed_at_ms=200, source="corrupt",
        payload={
            "schema_version": 1, "constraint_kind": "approval", "severity": "hard",
            "subject_type": "order", "subject_id": "o2", "state_key": "required",
        },
    ).as_event())
    with pytest.raises(BusinessConstraintHistoryInvariantViolation, match="subject id cannot be rewritten"):
        BusinessConstraintProjector(events).get(tenant_id="t", business_id="b", constraint_id="c")

    bad = MemoryEventStore()
    bad.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type="constraint.created", entity_id="c",
        event_time_ms=100, observed_at_ms=100, source="corrupt",
        payload={
            "schema_version": 2, "constraint_kind": "approval", "severity": "hard",
            "subject_type": None, "subject_id": None, "state_key": None,
        },
    ).as_event())
    with pytest.raises(BusinessConstraintHistoryInvariantViolation, match="unsupported schema_version"):
        BusinessConstraintProjector(bad).get(tenant_id="t", business_id="b", constraint_id="c")


def test_constraint_projection_is_scoped_and_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "constraint.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = BusinessConstraintRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="create",
            constraint_kind="approval", severity="hard", state_key="required", occurred_at_ms=100,
        )
        registry.update(
            tenant_id="tenant", business_id="business", constraint_id="constraint", idempotency_key="update",
            severity="soft", state_key="advisory", occurred_at_ms=200,
        )
    with SqliteEventStore(str(path)) as events:
        restored = BusinessConstraintProjector(events).get(
            tenant_id="tenant", business_id="business", constraint_id="constraint"
        )
        with pytest.raises(BusinessConstraintNotFound):
            BusinessConstraintProjector(events).get(
                tenant_id="tenant", business_id="other", constraint_id="constraint"
            )
    assert restored.severity is ConstraintSeverity.SOFT
    assert restored.state_key == "advisory"
