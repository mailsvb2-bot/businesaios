from __future__ import annotations

import pytest

from application.business_discovery.ingress import (
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
    ProviderBusinessObservationIngress,
)
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import StateSynthesisEngine
from runtime.state.state_snapshot_store import FileStateSnapshotStore
from storage.audit_store import InMemoryAuditStore
from storage.evidence_store import InMemoryEvidenceStore


def _runtime(tmp_path):
    events = MemoryEventStore()
    evidence = InMemoryEvidenceStore()
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    idempotency = InMemoryIdempotencyStore()
    owner = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=state,
        idempotency_store=idempotency,
    )
    provider = ProviderBusinessObservationIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=state,
    )
    audit = ProviderRuntimeAuditRecorder(
        audit_store=InMemoryAuditStore(),
        evidence_store=evidence,
    )
    return owner, provider, audit, state


def _owner_industry(owner: OwnerBusinessAssertionIngress, value: str = "medical_services") -> None:
    owner.ingest(
        assertion=OwnerBusinessAssertion(
            tenant_id="tenant-1",
            business_id="business-1",
            actor_id="owner-1",
            field_key="identity.industry",
            value=value,
            observed_at_ms=1_700_000_000_000,
        ),
        idempotency_key=f"owner-industry-{value}",
        recorded_at_ms=1_700_000_000_100,
    )


def _provider_evidence(
    audit: ProviderRuntimeAuditRecorder,
    *,
    value: str,
    mode: str = "live",
    business_id: str = "business-1",
):
    return audit.record_sync_run(
        tenant_id="tenant-1",
        business_id=business_id,
        provider_key="hubspot",
        operation="contact_sync",
        mode=mode,
        status="live_executed" if mode == "live" else "dry_run_ready",
        accepted=True,
        payload={},
        metadata={
            "business_observations": [
                {"field_key": "identity.industry", "value": value}
            ]
        },
    )


def test_provider_evidence_confirms_owner_assertion_through_canonical_state(tmp_path) -> None:
    owner, provider, audit, state = _runtime(tmp_path)
    _owner_industry(owner)
    refs = _provider_evidence(audit, value="medical_services")

    result = provider.reconcile(
        tenant_id="tenant-1",
        business_id="business-1",
        evidence_id=refs["evidence_id"],
    )

    assert result.verified_fields == ("identity.industry",)
    assert result.conflicted_fields == ()
    snapshot = state.snapshot_store.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    )
    field = snapshot.fields["business.profile.industry"]
    assert field.value == "medical_services"
    assert field.source == "provider:hubspot"
    assert field.conflict is False
    assert field.meta["epistemic_status"] == "VERIFIED"
    assert field.meta["observation_role"] == "PROVIDER_OBSERVED"
    assert [item.evidence_id for item in field.evidence_refs] == [refs["evidence_id"]]


def test_provider_evidence_conflict_remains_visible_and_provider_evidence_wins(tmp_path) -> None:
    owner, provider, audit, state = _runtime(tmp_path)
    _owner_industry(owner)
    refs = _provider_evidence(audit, value="retail")

    result = provider.reconcile(
        tenant_id="tenant-1",
        business_id="business-1",
        evidence_id=refs["evidence_id"],
    )

    assert result.verified_fields == ()
    assert result.conflicted_fields == ("identity.industry",)
    snapshot = state.snapshot_store.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    )
    field = snapshot.fields["business.profile.industry"]
    assert field.value == "retail"
    assert field.source == "provider:hubspot"
    assert field.conflict is True
    assert field.meta["epistemic_status"] == "CONFLICTED"
    conflict = next(
        item for item in snapshot.conflicts if item.field_path == "business.profile.industry"
    )
    assert set(conflict.candidate_sources) == {
        "business_discovery.owner_assertion",
        "provider:hubspot",
    }
    assert refs["evidence_id"] in conflict.resolution_evidence_refs


def test_provider_evidence_replay_is_idempotent(tmp_path) -> None:
    owner, provider, audit, _ = _runtime(tmp_path)
    _owner_industry(owner)
    refs = _provider_evidence(audit, value="medical_services")

    first = provider.reconcile(
        tenant_id="tenant-1",
        business_id="business-1",
        evidence_id=refs["evidence_id"],
    )
    replay = provider.reconcile(
        tenant_id="tenant-1",
        business_id="business-1",
        evidence_id=refs["evidence_id"],
    )

    assert replay.replayed is True
    assert replay.state_id == first.state_id


def test_provider_reconciliation_rejects_dry_run_and_cross_business_evidence(tmp_path) -> None:
    _, provider, audit, _ = _runtime(tmp_path)
    dry_run = _provider_evidence(audit, value="medical_services", mode="dry_run")
    with pytest.raises(ValueError, match="requires live provider evidence"):
        provider.reconcile(
            tenant_id="tenant-1",
            business_id="business-1",
            evidence_id=dry_run["evidence_id"],
        )

    other = _provider_evidence(
        audit,
        value="medical_services",
        business_id="business-other",
    )
    with pytest.raises(LookupError, match="provider evidence not found"):
        provider.reconcile(
            tenant_id="tenant-1",
            business_id="business-1",
            evidence_id=other["evidence_id"],
        )


def test_provider_reconciliation_rejects_unbound_provider_payload(tmp_path) -> None:
    _, provider, audit, _ = _runtime(tmp_path)
    refs = audit.record_sync_run(
        tenant_id="tenant-1",
        business_id="business-1",
        provider_key="hubspot",
        operation="contact_sync",
        mode="live",
        status="live_executed",
        accepted=True,
        payload={},
        metadata={},
    )

    with pytest.raises(ValueError, match="no canonical business observations"):
        provider.reconcile(
            tenant_id="tenant-1",
            business_id="business-1",
            evidence_id=refs["evidence_id"],
        )
