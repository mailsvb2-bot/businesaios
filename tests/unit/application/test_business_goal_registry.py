from __future__ import annotations

import pytest

from application.business_constraint import BusinessConstraintRegistry
from application.business_goal import BusinessGoalHistoryInvariantViolation, BusinessGoalProjector, BusinessGoalRegistry
from application.headless.goal_mapper import HeadlessGoalStateMapper
from application.headless.models import GoalExecutionRequest
from application.ontology import EventFactLifecycleWriter
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
    registry.archive(
        tenant_id="tenant",
        business_id="business",
        goal_id="parent",
        idempotency_key="parent-archive",
        occurred_at_ms=800,
    )
    count = len(events.events)
    replayed_child_create = registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="child",
        idempotency_key="child-create",
        goal_kind="acquisition",
        target_key="qualified_demand",
        parent_goal_id="parent",
        priority=60,
        occurred_at_ms=999,
    )
    assert replayed_child_create.lifecycle_status is GoalLifecycleStatus.COMPLETED
    assert len(events.events) == count


def test_goal_objective_fields_are_first_class_and_mutate_through_same_lifecycle() -> None:
    registry, events = _registry()
    constraints = BusinessConstraintRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    constraints.create(
        tenant_id="tenant",
        business_id="business",
        constraint_id="budget-cap",
        idempotency_key="constraint-budget-cap",
        constraint_kind="budget_guard",
        severity="hard",
        state_key="enforced",
        occurred_at_ms=10,
    )
    constraints.create(
        tenant_id="tenant",
        business_id="business",
        constraint_id="no-cold-calls",
        idempotency_key="constraint-no-cold-calls",
        constraint_kind="channel_guard",
        severity="hard",
        state_key="enforced",
        occurred_at_ms=20,
    )
    created = registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="profit",
        idempotency_key="create-profit",
        goal_kind="profitability",
        metric="net_profit",
        baseline=100_000,
        target=120_000,
        deadline_at_ms=1_000,
        owner_id="owner-1",
        constraint_ids=("budget-cap", "no-cold-calls"),
        priority=90,
        occurred_at_ms=100,
    )
    assert created.metric == "net_profit"
    assert created.target_key == "net_profit"
    assert created.baseline == 100_000.0
    assert created.target == 120_000.0
    assert created.deadline_at_ms == 1_000
    assert created.owner_id == "owner-1"
    assert created.constraint_ids == ("budget-cap", "no-cold-calls")

    updated = registry.update_objective(
        tenant_id="tenant",
        business_id="business",
        goal_id="profit",
        idempotency_key="revise-profit",
        target=125_000,
        deadline_at_ms=1_500,
        owner_id="owner-2",
        constraint_ids=("budget-cap",),
        priority=95,
        occurred_at_ms=200,
    )
    assert updated.metric == "net_profit"
    assert updated.baseline == 100_000.0
    assert updated.target == 125_000.0
    assert updated.deadline_at_ms == 1_500
    assert updated.owner_id == "owner-2"
    assert updated.constraint_ids == ("budget-cap",)
    assert updated.priority == 95

    count = len(events.events)
    assert registry.update_objective(
        tenant_id="tenant",
        business_id="business",
        goal_id="profit",
        idempotency_key="revise-profit",
        target=125_000,
        deadline_at_ms=1_500,
        owner_id="owner-2",
        constraint_ids=("budget-cap",),
        priority=95,
        occurred_at_ms=999,
    ) == updated
    assert len(events.events) == count


def test_goal_constraint_links_are_scope_validated_projected_and_replay_safe() -> None:
    registry, events = _registry()
    constraints = BusinessConstraintRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    constraints.create(
        tenant_id="tenant",
        business_id="business",
        constraint_id="active",
        idempotency_key="active-create",
        constraint_kind="budget_guard",
        severity="hard",
        state_key="enforced",
        occurred_at_ms=10,
    )
    constraints.create(
        tenant_id="tenant",
        business_id="other",
        constraint_id="foreign",
        idempotency_key="foreign-create",
        constraint_kind="approval",
        severity="hard",
        state_key="required",
        occurred_at_ms=20,
    )
    constraints.create(
        tenant_id="tenant",
        business_id="business",
        constraint_id="archived",
        idempotency_key="archived-create",
        constraint_kind="channel_guard",
        severity="soft",
        state_key="advisory",
        occurred_at_ms=30,
    )
    constraints.archive(
        tenant_id="tenant",
        business_id="business",
        constraint_id="archived",
        idempotency_key="archived-archive",
        occurred_at_ms=40,
    )

    with pytest.raises(ValueError, match="same business"):
        registry.create(
            tenant_id="tenant",
            business_id="business",
            goal_id="missing-link",
            idempotency_key="missing-link-create",
            goal_kind="growth",
            constraint_ids=("missing",),
            occurred_at_ms=100,
        )
    with pytest.raises(ValueError, match="same business"):
        registry.create(
            tenant_id="tenant",
            business_id="business",
            goal_id="foreign-link",
            idempotency_key="foreign-link-create",
            goal_kind="growth",
            constraint_ids=("foreign",),
            occurred_at_ms=100,
        )
    with pytest.raises(ValueError, match="archived constraints"):
        registry.create(
            tenant_id="tenant",
            business_id="business",
            goal_id="archived-link",
            idempotency_key="archived-link-create",
            goal_kind="growth",
            constraint_ids=("archived",),
            occurred_at_ms=100,
        )

    goal = registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="linked",
        idempotency_key="linked-create",
        goal_kind="growth",
        metric="mrr",
        constraint_ids=("active",),
        occurred_at_ms=100,
    )
    projector = BusinessGoalProjector(events)
    context = projector.load_context(
        tenant_id="tenant",
        business_id="business",
        goal_id="linked",
    )
    assert context["constraints"]["unresolved_ids"] == []
    assert context["constraints"]["evidence_only"] is True
    assert context["constraints"]["linked"] == [
        {
            "constraint_id": "active",
            "constraint_kind": "budget_guard",
            "severity": "hard",
            "subject_type": None,
            "subject_id": None,
            "state_key": "enforced",
            "lifecycle_status": "active",
            "updated_at_ms": 10,
        }
    ]

    state = HeadlessGoalStateMapper(canonical_goal_reader=projector).to_world_state(
        request=GoalExecutionRequest(
            goal="Grow recurring revenue within the canonical guard",
            goal_id="linked",
            tenant_id="tenant",
            business_id="business",
        ),
        step_index=0,
        previous_feedback={},
    )
    assert state.meta["canonical_goal"]["constraints"]["linked"][0]["constraint_id"] == "active"

    constraints.archive(
        tenant_id="tenant",
        business_id="business",
        constraint_id="active",
        idempotency_key="active-archive",
        occurred_at_ms=200,
    )
    archived_context = projector.load_context(
        tenant_id="tenant",
        business_id="business",
        goal_id="linked",
    )
    assert archived_context["constraints"]["linked"][0]["lifecycle_status"] == "archived"

    before = list(events.events)
    replayed = registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="linked",
        idempotency_key="linked-create",
        goal_kind="growth",
        metric="mrr",
        constraint_ids=("active",),
        occurred_at_ms=999,
    )
    assert replayed == goal
    assert events.events == before

    with pytest.raises(ValueError, match="same business"):
        registry.update_objective(
            tenant_id="tenant",
            business_id="business",
            goal_id="linked",
            idempotency_key="missing-update",
            constraint_ids=("missing",),
            occurred_at_ms=210,
        )
    with pytest.raises(ValueError, match="same business"):
        registry.update_objective(
            tenant_id="tenant",
            business_id="business",
            goal_id="linked",
            idempotency_key="foreign-update",
            constraint_ids=("foreign",),
            occurred_at_ms=210,
        )
    with pytest.raises(ValueError, match="archived constraints"):
        registry.update_objective(
            tenant_id="tenant",
            business_id="business",
            goal_id="linked",
            idempotency_key="archived-update",
            constraint_ids=("archived",),
            occurred_at_ms=210,
        )

    constraints.create(
        tenant_id="tenant",
        business_id="business",
        constraint_id="replacement",
        idempotency_key="replacement-create",
        constraint_kind="approval",
        severity="hard",
        state_key="required",
        occurred_at_ms=220,
    )
    updated = registry.update_objective(
        tenant_id="tenant",
        business_id="business",
        goal_id="linked",
        idempotency_key="replacement-link",
        constraint_ids=("replacement",),
        occurred_at_ms=230,
    )
    assert updated.constraint_ids == ("replacement",)
    constraints.archive(
        tenant_id="tenant",
        business_id="business",
        constraint_id="replacement",
        idempotency_key="replacement-archive",
        occurred_at_ms=240,
    )
    before_update_replay = list(events.events)
    assert registry.update_objective(
        tenant_id="tenant",
        business_id="business",
        goal_id="linked",
        idempotency_key="replacement-link",
        constraint_ids=("replacement",),
        occurred_at_ms=999,
    ) == updated
    assert events.events == before_update_replay


def test_goal_context_keeps_historical_unresolved_constraint_as_evidence() -> None:
    events = MemoryEventStore()
    writer = EventFactLifecycleWriter(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
        namespace="business_goal_fact",
        source="business_goal_registry",
        id_prefix="business-goal",
    )
    writer.append_once(
        tenant_id="tenant",
        business_id="business",
        entity_id="legacy-goal",
        operation="create",
        idempotency_key="legacy-linked-create",
        fact_type="goal.created",
        payload={
            "schema_version": 1,
            "goal_kind": "growth",
            "target_key": "mrr",
            "metric": "mrr",
            "constraint_ids": ["retired-or-missing"],
            "parent_goal_id": None,
            "priority": 50,
        },
        occurred_at_ms=100,
    )
    context = BusinessGoalProjector(events).load_context(
        tenant_id="tenant",
        business_id="business",
        goal_id="legacy-goal",
    )
    assert context["constraints"]["linked"] == []
    assert context["constraints"]["unresolved_ids"] == ["retired-or-missing"]
    assert context["constraints"]["evidence_only"] is True


def test_goal_context_projects_deterministic_cross_goal_conflicts_without_ranking() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant", business_id="business", goal_id="increase", idempotency_key="increase",
        goal_kind="growth", metric="mrr", baseline=100.0, target=120.0, priority=90, occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant", business_id="business", goal_id="decrease", idempotency_key="decrease",
        goal_kind="efficiency", metric="mrr", baseline=100.0, target=80.0, priority=80, occurred_at_ms=110,
    )
    registry.create(
        tenant_id="tenant", business_id="business", goal_id="increase-more", idempotency_key="increase-more",
        goal_kind="growth", metric="mrr", baseline=100.0, target=140.0, priority=70, occurred_at_ms=120,
    )
    projector = BusinessGoalProjector(events)
    context = projector.load_context(tenant_id="tenant", business_id="business", goal_id="increase")

    assert context["conflicts"]["goal_goal"] == [
        {
            "conflict_kind": "opposing_goal_direction",
            "metric": "mrr",
            "goal_id": "increase",
            "other_goal_id": "decrease",
            "goal_direction": "increase",
            "other_direction": "decrease",
            "goal_target": 120.0,
            "other_target": 80.0,
        }
    ]
    assert context["conflicts"]["goal_constraint"] == []
    assert context["conflicts"]["has_conflicts"] is True
    assert context["conflicts"]["deterministic_only"] is True
    assert "selected_goal_id" not in context["conflicts"]

    state = HeadlessGoalStateMapper(canonical_goal_reader=projector).to_world_state(
        request=GoalExecutionRequest(
            goal="Increase MRR without silently overriding conflicting objectives",
            goal_id="increase",
            tenant_id="tenant",
            business_id="business",
        ),
        step_index=0,
        previous_feedback={},
    )
    assert state.meta["canonical_goal"]["conflicts"]["goal_goal"][0]["other_goal_id"] == "decrease"


def test_metric_scoped_constraint_projects_as_guard_metric_without_semantic_guessing() -> None:
    registry, events = _registry()
    constraints = BusinessConstraintRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    constraints.create(
        tenant_id="tenant",
        business_id="business",
        constraint_id="complaints-guard",
        idempotency_key="complaints-guard-create",
        constraint_kind="guard_metric",
        severity="hard",
        subject_type="metric",
        subject_id="complaints",
        state_key="must_not_increase",
        occurred_at_ms=10,
    )
    registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="sales",
        idempotency_key="sales-create",
        goal_kind="growth",
        metric="revenue",
        baseline=100.0,
        target=120.0,
        constraint_ids=("complaints-guard",),
        occurred_at_ms=100,
    )

    context = BusinessGoalProjector(events).load_context(
        tenant_id="tenant", business_id="business", goal_id="sales"
    )
    assert context["conflicts"]["goal_constraint"] == []
    assert context["constraints"]["guard_metrics"] == [
        {
            "metric": "complaints",
            "constraint_id": "complaints-guard",
            "constraint_kind": "guard_metric",
            "severity": "hard",
            "state_key": "must_not_increase",
            "lifecycle_status": "active",
        }
    ]
    assert context["constraints"]["evidence_only"] is True


def test_goal_hierarchy_reaches_canonical_headless_world_state() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="profit",
        idempotency_key="profit",
        goal_kind="profitability",
        metric="net_profit",
        baseline=100_000,
        target=120_000,
        priority=90,
        occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="conversion",
        idempotency_key="conversion",
        goal_kind="conversion",
        metric="conversion_rate",
        baseline=0.20,
        target=0.25,
        parent_goal_id="profit",
        priority=80,
        occurred_at_ms=200,
    )
    projector = BusinessGoalProjector(events)
    context = projector.load_context(
        tenant_id="tenant",
        business_id="business",
        goal_id="conversion",
    )
    assert context["goal"]["goal_id"] == "conversion"
    assert context["hierarchy"]["depth"] == 1
    assert [row["goal_id"] for row in context["hierarchy"]["ancestors"]] == ["profit"]

    state = HeadlessGoalStateMapper(canonical_goal_reader=projector).to_world_state(
        request=GoalExecutionRequest(
            goal="Increase conversion without losing profit",
            goal_id="conversion",
            tenant_id="tenant",
            business_id="business",
        ),
        step_index=0,
        previous_feedback={},
    )
    assert state.meta["goal_id"] == "conversion"
    assert state.meta["canonical_goal"]["goal"]["metric"] == "conversion_rate"
    assert (
        state.meta["canonical_goal"]["hierarchy"]["ancestors"][0]["goal_id"]
        == "profit"
    )
    assert state.behavior["goal_id"] == "conversion"


def test_goal_objective_replays_pre_phase6_payload_without_rewriting_history() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    legacy_writer = EventFactLifecycleWriter(
        event_store=events,
        idempotency_store=claims,
        namespace="business_goal_fact",
        source="business_goal_registry",
        id_prefix="business-goal",
    )
    legacy_writer.append_once(
        tenant_id="tenant",
        business_id="business",
        entity_id="goal",
        operation="create",
        idempotency_key="legacy-create",
        fact_type="goal.created",
        payload={
            "schema_version": 1,
            "goal_kind": "growth",
            "target_key": "mrr",
            "parent_goal_id": None,
            "priority": 50,
        },
        occurred_at_ms=100,
    )
    legacy_writer.append_once(
        tenant_id="tenant",
        business_id="business",
        entity_id="goal",
        operation="update",
        idempotency_key="legacy-update",
        fact_type="goal.updated",
        payload={
            "schema_version": 1,
            "goal_kind": "growth",
            "target_key": "mrr",
            "parent_goal_id": None,
            "priority": 80,
        },
        occurred_at_ms=200,
    )

    registry = BusinessGoalRegistry(event_store=events, idempotency_store=claims)
    restored = registry.get(tenant_id="tenant", business_id="business", goal_id="goal")
    assert restored.metric == "mrr"
    assert restored.priority == 80
    before = list(events.events)

    replayed_create = registry.create(
        tenant_id="tenant",
        business_id="business",
        goal_id="goal",
        idempotency_key="legacy-create",
        goal_kind="growth",
        target_key="mrr",
        priority=50,
        occurred_at_ms=999,
    )
    assert replayed_create == restored
    assert events.events == before

    replayed = registry.update_objective(
        tenant_id="tenant",
        business_id="business",
        goal_id="goal",
        idempotency_key="legacy-update",
        priority=80,
        occurred_at_ms=999,
    )
    assert replayed == restored
    assert events.events == before

    with pytest.raises(ValueError, match="different objective data"):
        registry.update_objective(
            tenant_id="tenant",
            business_id="business",
            goal_id="goal",
            idempotency_key="legacy-update",
            priority=70,
            occurred_at_ms=999,
        )
    assert events.events == before


def test_goal_objective_contract_rejects_conflicting_metric_and_invalid_values() -> None:
    with pytest.raises(ValueError, match="same canonical metric"):
        BusinessGoal(
            goal_id="g",
            tenant_id="t",
            business_id="b",
            goal_kind="growth",
            target_key="mrr",
            metric="revenue",
        )
    with pytest.raises(ValueError, match="finite number"):
        BusinessGoal(
            goal_id="g",
            tenant_id="t",
            business_id="b",
            goal_kind="growth",
            metric="mrr",
            target=float("nan"),
        )
    with pytest.raises(ValueError, match="deadline_at_ms must be >= created_at_ms"):
        BusinessGoal(
            goal_id="g",
            tenant_id="t",
            business_id="b",
            goal_kind="growth",
            metric="mrr",
            created_at_ms=100,
            updated_at_ms=100,
            deadline_at_ms=99,
        )
    with pytest.raises(ValueError, match="constraint_ids must be unique"):
        BusinessGoal(
            goal_id="g",
            tenant_id="t",
            business_id="b",
            goal_kind="growth",
            metric="mrr",
            constraint_ids=("c1", "c1"),
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
    assert restored.metric == "mrr"
    assert restored.priority == 85
