from __future__ import annotations

import pytest

from application.business_goal import BusinessGoalHistoryInvariantViolation, BusinessGoalProjector, BusinessGoalRegistry
from contracts.business_goal import BusinessGoal, BusinessGoalNotFound, GoalLifecycleStatus
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
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
    return BusinessGoalRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_goal_hierarchy_lifecycle_and_idempotency() -> None:
    registry, events = _registry()
    parent = registry.create(
        tenant_id="tenant", business_id="business", goal_id="parent", idempotency_key="parent-create",
        goal_kind="growth", target_key="mrr", priority=80, occurred_at_ms=100,
    )
    assert parent.lifecycle_status is GoalLifecycleStatus.ACTIVE
    child = registry.create(
        tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="child-create",
        goal_kind="acquisition", target_key="qualified_demand", parent_goal_id="parent", priority=60,
        occurred_at_ms=200,
    )
    count = len(events.events)
    assert registry.create(
        tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="child-create",
        goal_kind="acquisition", target_key="qualified_demand", parent_goal_id="parent", priority=60,
        occurred_at_ms=999,
    ) == child
    assert len(events.events) == count
    updated = registry.update_priority(
        tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="priority",
        priority=90, occurred_at_ms=300,
    )
    assert updated.priority == 90
    completed = registry.complete(
        tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="complete",
        occurred_at_ms=400,
    )
    assert completed.lifecycle_status is GoalLifecycleStatus.COMPLETED
    assert completed.terminal_at_ms == 400
    with pytest.raises(ValueError, match="terminal business goal"):
        registry.update_priority(
            tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="late",
            priority=10, occurred_at_ms=500,
        )
    assert registry.complete(
        tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="complete-again",
        occurred_at_ms=600,
    ) == completed
    with pytest.raises(ValueError, match="cannot change terminal status"):
        registry.cancel(
            tenant_id="tenant", business_id="business", goal_id="child", idempotency_key="conflict",
            occurred_at_ms=700,
        )


def test_goal_metadata_propagates_and_same_key_replay_rejects_change() -> None:
    registry, events = _registry()
    create_metadata = { "actor_id": "owner-1", "decision_id": "decision-create", "evidence_ids": ("goal-evidence-1",), }
    created = registry.create( tenant_id="t", business_id="b", goal_id="g", idempotency_key="create-meta", goal_kind="growth", target_key="mrr", priority=50, occurred_at_ms=100, event_metadata=create_metadata, )
    assert registry.create( tenant_id="t", business_id="b", goal_id="g", idempotency_key="create-meta", goal_kind="growth", target_key="mrr", priority=50, occurred_at_ms=999, event_metadata=create_metadata, ) == created
    assert canonical_business_event_contract(events.events[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        registry.create( tenant_id="t", business_id="b", goal_id="g", idempotency_key="create-meta", goal_kind="growth", target_key="mrr", priority=50, occurred_at_ms=100, event_metadata={**create_metadata, "actor_id": "owner-2"}, )
    update_metadata = {"actor_id": "owner-1", "decision_id": "decision-update"}
    updated = registry.update_priority( tenant_id="t", business_id="b", goal_id="g", idempotency_key="update-meta", priority=80, occurred_at_ms=200, event_metadata=update_metadata, )
    assert registry.update_priority( tenant_id="t", business_id="b", goal_id="g", idempotency_key="update-meta", priority=80, occurred_at_ms=999, event_metadata=update_metadata, ) == updated
    with pytest.raises(ValueError, match="event metadata"):
        registry.update_priority( tenant_id="t", business_id="b", goal_id="g", idempotency_key="update-meta", priority=80, occurred_at_ms=200, event_metadata={**update_metadata, "actor_id": "owner-2"}, )
    terminal_metadata = {"actor_id": "owner-1", "decision_id": "decision-complete"}
    completed = registry.complete( tenant_id="t", business_id="b", goal_id="g", idempotency_key="complete-meta", occurred_at_ms=300, event_metadata=terminal_metadata, )
    assert registry.complete( tenant_id="t", business_id="b", goal_id="g", idempotency_key="complete-meta", occurred_at_ms=999, event_metadata=terminal_metadata, ) == completed
    with pytest.raises(ValueError, match="event metadata"):
        registry.complete( tenant_id="t", business_id="b", goal_id="g", idempotency_key="complete-meta", occurred_at_ms=300, event_metadata={**terminal_metadata, "actor_id": "owner-2"}, )


def test_goal_parent_relation_is_same_scope_and_fail_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant", business_id="a", goal_id="parent", idempotency_key="p",
        goal_kind="growth", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="same business"):
        registry.create(
            tenant_id="tenant", business_id="b", goal_id="child", idempotency_key="c",
            goal_kind="growth", parent_goal_id="parent", occurred_at_ms=200,
        )
    registry.cancel(
        tenant_id="tenant", business_id="a", goal_id="parent", idempotency_key="cancel", occurred_at_ms=300,
    )
    with pytest.raises(ValueError, match="cancelled or archived"):
        registry.create(
            tenant_id="tenant", business_id="a", goal_id="child-2", idempotency_key="c2",
            goal_kind="growth", parent_goal_id="parent", occurred_at_ms=400,
        )


def test_goal_contract_rejects_invalid_priority_and_self_parent() -> None:
    with pytest.raises(ValueError, match="priority"):
        BusinessGoal(goal_id="g", tenant_id="t", business_id="b", goal_kind="growth", priority=101)
    with pytest.raises(ValueError, match="own parent"):
        BusinessGoal(goal_id="g", tenant_id="t", business_id="b", goal_kind="growth", parent_goal_id="g")


def test_goal_projection_rejects_corrupt_schema_and_post_terminal_history() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type="goal.created", entity_id="g",
        event_time_ms=100, observed_at_ms=100, source="business_goal_registry",
        payload={"schema_version": 2, "goal_kind": "growth", "target_key": None, "parent_goal_id": None, "priority": 50},
    ).as_event())
    with pytest.raises(BusinessGoalHistoryInvariantViolation, match="unsupported schema_version"):
        BusinessGoalProjector(events).get(tenant_id="t", business_id="b", goal_id="g")

    registry, clean = _registry()
    registry.create(
        tenant_id="t", business_id="b", goal_id="g", idempotency_key="create", goal_kind="growth", occurred_at_ms=100,
    )
    registry.complete(tenant_id="t", business_id="b", goal_id="g", idempotency_key="done", occurred_at_ms=200)
    clean.append_event(BusinessFactV1(
        fact_id="late", tenant_id="t", business_id="b", fact_type="goal.updated", entity_id="g",
        event_time_ms=300, observed_at_ms=300, source="corrupt",
        payload={"schema_version": 1, "goal_kind": "growth", "target_key": None, "parent_goal_id": None, "priority": 10},
    ).as_event())
    with pytest.raises(BusinessGoalHistoryInvariantViolation, match="continues after terminal"):
        BusinessGoalProjector(clean).get(tenant_id="t", business_id="b", goal_id="g")


def test_goal_projection_is_scoped_and_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "goal.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = BusinessGoalRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant", business_id="business", goal_id="goal", idempotency_key="create",
            goal_kind="growth", target_key="mrr", priority=70, occurred_at_ms=100,
        )
        registry.update_priority(
            tenant_id="tenant", business_id="business", goal_id="goal", idempotency_key="update",
            priority=85, occurred_at_ms=200,
        )
    with SqliteEventStore(str(path)) as events:
        restored = BusinessGoalProjector(events).get(tenant_id="tenant", business_id="business", goal_id="goal")
        with pytest.raises(BusinessGoalNotFound):
            BusinessGoalProjector(events).get(tenant_id="tenant", business_id="other", goal_id="goal")
    assert restored.target_key == "mrr"
    assert restored.priority == 85
