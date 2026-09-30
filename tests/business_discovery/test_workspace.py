from __future__ import annotations

from application.business_discovery import (
    BusinessDiscoveryWorkspace,
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
)
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import StateSynthesisEngine
from runtime.state.state_snapshot_store import FileStateSnapshotStore
from storage.evidence_store import InMemoryEvidenceStore


def _workspace(tmp_path) -> BusinessDiscoveryWorkspace:
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    ingress = OwnerBusinessAssertionIngress(
        event_store=MemoryEventStore(),
        evidence_store=InMemoryEvidenceStore(),
        state_engine=state,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    return BusinessDiscoveryWorkspace(ingress=ingress, state_engine=state)


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
