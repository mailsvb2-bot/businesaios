from __future__ import annotations

import pytest

from application.business_constraint import BusinessConstraintRegistry
from application.business_discovery import (
    BusinessDiscoveryWorkspace,
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
)
from application.business_goal import BusinessGoalRegistry
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import StateSynthesisEngine
from runtime.state.state_snapshot_store import FileStateSnapshotStore
from storage.evidence_store import InMemoryEvidenceStore


def _workspace(tmp_path) -> BusinessDiscoveryWorkspace:
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    events = MemoryEventStore()
    idempotency = InMemoryIdempotencyStore()
    ingress = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=InMemoryEvidenceStore(),
        state_engine=state,
        idempotency_store=idempotency,
    )
    return BusinessDiscoveryWorkspace(
        ingress=ingress,
        state_engine=state,
        goal_registry=BusinessGoalRegistry(
            event_store=events,
            idempotency_store=idempotency,
        ),
        constraint_registry=BusinessConstraintRegistry(
            event_store=events,
            idempotency_store=idempotency,
        ),
    )


def test_discovery_workspace_reads_progress_from_canonical_state(tmp_path) -> None:
    workspace = _workspace(tmp_path)

    empty = workspace.describe(tenant_id="tenant-1", business_id="business-1")
    assert empty["state_id"] is None
    assert empty["progress"]["covered_fields"] == 0
    assert empty["progress"]["remaining_fields"] == empty["progress"]["total_fields"]
    assert empty["progress"]["next_field_key"] == "identity.display_name"

    updated = workspace.assert_owner(
        assertion=OwnerBusinessAssertion(
            tenant_id="tenant-1",
            business_id="business-1",
            actor_id="owner-1",
            field_key="identity.display_name",
            value="  Canonical Business  ",
            observed_at_ms=1_700_000_000_000,
        ),
        idempotency_key="display-name-1",
        recorded_at_ms=1_700_000_000_100,
    )

    display = next(item for item in updated["fields"] if item["key"] == "identity.display_name")
    assert display["value"] == "Canonical Business"
    assert display["status"] == "known"
    assert display["covered"] is True
    assert display["owner_asserted"] is True
    assert len(display["evidence_ids"]) == 1
    assert updated["progress"]["covered_fields"] == 1
    assert updated["progress"]["owner_asserted_fields"] == 1
    assert updated["progress"]["next_field_key"] == "identity.website"


def test_discovery_workspace_unknown_counts_as_explicitly_covered(tmp_path) -> None:
    workspace = _workspace(tmp_path)

    updated = workspace.assert_owner(
        assertion=OwnerBusinessAssertion(
            tenant_id="tenant-1",
            business_id="business-1",
            actor_id="owner-1",
            field_key="economics.margin_pct",
            value=None,
            unknown=True,
            observed_at_ms=1_700_000_000_000,
        ),
        idempotency_key="margin-unknown-1",
        recorded_at_ms=1_700_000_000_100,
    )

    margin = next(item for item in updated["fields"] if item["key"] == "economics.margin_pct")
    assert margin["status"] == "unknown"
    assert margin["covered"] is True
    assert margin["owner_asserted"] is True



def test_discovery_goal_and_constraint_provenance_uses_canonical_event_metadata(tmp_path) -> None:
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state-provenance")
    )
    events = MemoryEventStore()
    idempotency = InMemoryIdempotencyStore()
    workspace = BusinessDiscoveryWorkspace(
        ingress=OwnerBusinessAssertionIngress(
            event_store=events,
            evidence_store=InMemoryEvidenceStore(),
            state_engine=state,
            idempotency_store=idempotency,
        ),
        state_engine=state,
        goal_registry=BusinessGoalRegistry(
            event_store=events,
            idempotency_store=idempotency,
        ),
        constraint_registry=BusinessConstraintRegistry(
            event_store=events,
            idempotency_store=idempotency,
        ),
    )

    workspace.create_constraint(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
        idempotency_key="constraint-provenance-1",
        confirmed=True,
        constraint_id="constraint-provenance",
        constraint_kind="metric_floor",
        severity="hard",
        subject_type="metric",
        subject_id="gross_margin_pct",
        comparison="gte",
        threshold=20.0,
        occurred_at_ms=1_700_000_000_000,
    )
    workspace.create_goal(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
        idempotency_key="goal-provenance-1",
        confirmed=True,
        goal_id="goal-provenance",
        goal_kind="improve_margin",
        metric="gross_margin_pct",
        baseline=20.0,
        target=30.0,
        constraint_ids=("constraint-provenance",),
        occurred_at_ms=1_700_000_000_100,
    )

    facts = [
        dict(event.get("payload") or {})
        for event in events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        )
        if dict(event.get("payload") or {}).get("fact_type")
        in {"constraint.created", "goal.created"}
    ]
    assert len(facts) == 2
    assert all(item["actor_id"] == "owner-1" for item in facts)
    assert all(
        item["provenance"]
        == {"ingress": "business_discovery", "owner_confirmed": True}
        for item in facts
    )


def test_discovery_goal_and_constraint_use_canonical_registries_and_require_confirmation(tmp_path) -> None:
    workspace = _workspace(tmp_path)

    constraint = workspace.create_constraint(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
        idempotency_key="constraint-1",
        confirmed=True,
        constraint_id="constraint-margin-floor",
        constraint_kind="metric_floor",
        severity="hard",
        subject_type="metric",
        subject_id="gross_margin_pct",
        comparison="gte",
        threshold=30.0,
        occurred_at_ms=1_700_000_000_000,
    )
    assert constraint["constraint_id"] == "constraint-margin-floor"
    assert constraint["comparison"] == "gte"
    assert constraint["threshold"] == 30.0

    goal = workspace.create_goal(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
        idempotency_key="goal-1",
        confirmed=True,
        goal_id="goal-margin",
        goal_kind="improve_margin",
        metric="gross_margin_pct",
        baseline=25.0,
        target=35.0,
        constraint_ids=("constraint-margin-floor",),
        priority=80,
        occurred_at_ms=1_700_000_000_100,
    )
    assert goal["goal_id"] == "goal-margin"
    assert goal["owner_id"] == "owner-1"
    assert tuple(goal["constraint_ids"]) == ("constraint-margin-floor",)
    assert [item["goal_id"] for item in workspace.list_goals(
        tenant_id="tenant-1",
        business_id="business-1",
    )] == ["goal-margin"]

    with pytest.raises(ValueError, match="explicit owner confirmation"):
        workspace.create_goal(
            tenant_id="tenant-1",
            business_id="business-1",
            actor_id="owner-1",
            idempotency_key="goal-unconfirmed",
            confirmed=False,
            goal_id="goal-unconfirmed",
            goal_kind="free_text_guess",
        )
