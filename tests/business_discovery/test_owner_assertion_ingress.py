from __future__ import annotations

import pytest

from application.business_discovery import (
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import StateSynthesisEngine
from runtime.state.state_snapshot_store import FileStateSnapshotStore
from storage.evidence_store import InMemoryEvidenceStore


def _ingress(tmp_path):
    events = MemoryEventStore()
    evidence = InMemoryEvidenceStore()
    snapshots = FileStateSnapshotStore(tmp_path / "state")
    state = StateSynthesisEngine(snapshot_store=snapshots)
    ingress = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=state,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    return ingress, events, evidence, snapshots


def _assertion(**overrides):
    values = {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "actor_id": "owner-1",
        "field_key": "identity.industry",
        "value": "medical_services",
        "observed_at_ms": 1_700_000_000_000,
        "correlation_id": "corr-1",
    }
    values.update(overrides)
    return OwnerBusinessAssertion(**values)


def test_owner_assertion_flows_through_evidence_fact_and_semantic_state(tmp_path) -> None:
    ingress, events, evidence, snapshots = _ingress(tmp_path)

    result = ingress.ingest(
        assertion=_assertion(),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )

    [event] = list(
        events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        )
    )
    assert event["event_id"] == result.fact_id
    assert event["source"] == "business_discovery.owner_assertion"
    envelope = event["payload"]
    assert envelope["actor_id"] == "owner-1"
    assert envelope["fact_type"] == "business.discovery.identity.industry"
    assert envelope["payload"]["value"] == "medical_services"
    assert envelope["provenance"]["epistemic_status"] == "OWNER_ASSERTED"
    assert envelope["provenance"]["authoritative"] is False

    stored_evidence = evidence.get(
        tenant_id="tenant-1",
        evidence_id=result.evidence_id,
    )
    assert stored_evidence is not None
    assert stored_evidence.source_type == "owner_assertion"
    assert stored_evidence.verification_status == "asserted"

    snapshot = snapshots.load_latest(tenant_id="tenant-1", business_id="business-1")
    assert snapshot is not None
    assert snapshot.state_id == result.state_id
    assert snapshot.values["business"]["profile"]["industry"] == "medical_services"
    field = snapshot.fields["business.profile.industry"]
    assert field.semantic_kind == "fact"
    assert field.authoritative is False
    assert field.meta["business_discovery_fact_id"] == result.fact_id
    assert field.meta["epistemic_status"] == "OWNER_ASSERTED"
    assert [item.evidence_id for item in field.evidence_refs] == [result.evidence_id]


def test_owner_assertion_exact_replay_is_idempotent(tmp_path) -> None:
    ingress, events, evidence, snapshots = _ingress(tmp_path)
    assertion = _assertion()

    first = ingress.ingest(
        assertion=assertion,
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )
    second = ingress.ingest(
        assertion=assertion,
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_999_999,
    )

    assert second.replayed is True
    assert second.fact_id == first.fact_id
    assert second.evidence_id == first.evidence_id
    assert second.state_id == first.state_id
    assert len(
        list(
            events.iter_events(
                tenant_id="tenant-1",
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        )
    ) == 1
    assert len(evidence.list_for_tenant(tenant_id="tenant-1")) == 1
    assert snapshots.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    ).state_id == first.state_id


def test_owner_assertion_same_idempotency_key_cannot_change_meaning(tmp_path) -> None:
    ingress, events, evidence, _ = _ingress(tmp_path)
    ingress.ingest(
        assertion=_assertion(),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )

    with pytest.raises(ValueError, match="different assertion"):
        ingress.ingest(
            assertion=_assertion(value="retail"),
            idempotency_key="owner-form-1",
            recorded_at_ms=1_700_000_000_200,
        )

    assert len(
        list(
            events.iter_events(
                tenant_id="tenant-1",
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        )
    ) == 1
    assert len(evidence.list_for_tenant(tenant_id="tenant-1")) == 1


def test_owner_assertion_same_idempotency_key_cannot_move_to_another_field(tmp_path) -> None:
    ingress, events, evidence, _ = _ingress(tmp_path)
    ingress.ingest(
        assertion=_assertion(),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )

    with pytest.raises(ValueError, match="different assertion"):
        ingress.ingest(
            assertion=_assertion(
                field_key="market.region",
                value="Nizhny Novgorod",
            ),
            idempotency_key="owner-form-1",
            recorded_at_ms=1_700_000_000_200,
        )

    assert len(
        list(
            events.iter_events(
                tenant_id="tenant-1",
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        )
    ) == 1
    assert len(evidence.list_for_tenant(tenant_id="tenant-1")) == 1


def test_owner_assertion_rejects_observation_from_after_recording_time(tmp_path) -> None:
    ingress, events, evidence, snapshots = _ingress(tmp_path)

    with pytest.raises(ValueError, match="observed_at_ms must not follow recorded_at_ms"):
        ingress.ingest(
            assertion=_assertion(observed_at_ms=1_700_000_000_200),
            idempotency_key="future-observation",
            recorded_at_ms=1_700_000_000_100,
        )

    assert list(
        events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        )
    ) == []
    assert evidence.list_for_tenant(tenant_id="tenant-1") == ()
    assert snapshots.load_latest(tenant_id="tenant-1", business_id="business-1") is None


def test_owner_assertion_same_idempotency_key_cannot_change_observation_time(tmp_path) -> None:
    ingress, events, evidence, _ = _ingress(tmp_path)
    ingress.ingest(
        assertion=_assertion(),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )

    with pytest.raises(ValueError, match="different assertion"):
        ingress.ingest(
            assertion=_assertion(observed_at_ms=1_700_000_000_001),
            idempotency_key="owner-form-1",
            recorded_at_ms=1_700_000_000_200,
        )

    assert len(
        list(
            events.iter_events(
                tenant_id="tenant-1",
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        )
    ) == 1
    assert len(evidence.list_for_tenant(tenant_id="tenant-1")) == 1


def test_owner_assertion_same_idempotency_key_cannot_change_occurrence_time(tmp_path) -> None:
    ingress, events, evidence, _ = _ingress(tmp_path)
    ingress.ingest(
        assertion=_assertion(occurred_at_ms=1_699_999_999_900),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )

    with pytest.raises(ValueError, match="different assertion"):
        ingress.ingest(
            assertion=_assertion(occurred_at_ms=1_699_999_999_800),
            idempotency_key="owner-form-1",
            recorded_at_ms=1_700_000_000_200,
        )

    assert len(
        list(
            events.iter_events(
                tenant_id="tenant-1",
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        )
    ) == 1
    assert len(evidence.list_for_tenant(tenant_id="tenant-1")) == 1


def test_owner_assertion_unknown_is_fact_semantics_not_parallel_epistemic_layer(tmp_path) -> None:
    ingress, _, _, snapshots = _ingress(tmp_path)

    result = ingress.ingest(
        assertion=_assertion(
            field_key="economics.margin_pct",
            value=None,
            unknown=True,
        ),
        idempotency_key="owner-margin-unknown",
        recorded_at_ms=1_700_000_000_100,
    )

    snapshot = snapshots.load_latest(tenant_id="tenant-1", business_id="business-1")
    field = snapshot.fields[result.field_path]
    assert field.semantic_kind == "fact"
    assert field.value_kind == "unknown"
    assert field.value is None


def test_owner_assertion_replay_recovers_missing_semantic_snapshot(tmp_path) -> None:
    ingress, _, _, snapshots = _ingress(tmp_path)
    assertion = _assertion()

    first = ingress.ingest(
        assertion=assertion,
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )
    snapshot_path = snapshots._path(tenant_id="tenant-1", business_id="business-1")
    snapshot_path.unlink()

    recovered = ingress.ingest(
        assertion=assertion,
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_100,
    )
    assert recovered.replayed is True
    assert recovered.fact_id == first.fact_id
    assert snapshots.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    ).fields["business.profile.industry"].value == "medical_services"


def test_owner_assertion_replay_repairs_stale_existing_snapshot(tmp_path) -> None:
    ingress, _, _, snapshots = _ingress(tmp_path)
    snapshot_path = snapshots._path(tenant_id="tenant-1", business_id="business-1")

    ingress.ingest(
        assertion=_assertion(
            field_key="market.region",
            value="Nizhny Novgorod",
        ),
        idempotency_key="owner-region-1",
        recorded_at_ms=1_700_000_000_100,
    )
    stale_snapshot = snapshot_path.read_bytes()

    first = ingress.ingest(
        assertion=_assertion(),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_200,
    )
    assert snapshots.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    ).fields["business.profile.industry"].value == "medical_services"

    snapshot_path.write_bytes(stale_snapshot)

    recovered = ingress.ingest(
        assertion=_assertion(),
        idempotency_key="owner-form-1",
        recorded_at_ms=1_700_000_000_200,
    )

    assert recovered.replayed is True
    assert recovered.fact_id == first.fact_id
    repaired = snapshots.load_latest(tenant_id="tenant-1", business_id="business-1")
    assert repaired.fields["business.profile.industry"].value == "medical_services"
    assert (
        repaired.fields["business.profile.industry"].meta["business_discovery_fact_id"]
        == first.fact_id
    )


def test_owner_assertion_scope_is_tenant_and_business_isolated(tmp_path) -> None:
    ingress, _, evidence, snapshots = _ingress(tmp_path)
    first = ingress.ingest(
        assertion=_assertion(),
        idempotency_key="same-browser-key",
        recorded_at_ms=1_700_000_000_100,
    )
    second = ingress.ingest(
        assertion=_assertion(
            tenant_id="tenant-2",
            business_id="business-2",
            actor_id="owner-2",
            value="retail",
        ),
        idempotency_key="same-browser-key",
        recorded_at_ms=1_700_000_000_200,
    )

    assert first.fact_id != second.fact_id
    assert evidence.get(tenant_id="tenant-2", evidence_id=first.evidence_id) is None
    assert snapshots.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    ).values["business"]["profile"]["industry"] == "medical_services"
    assert snapshots.load_latest(
        tenant_id="tenant-2",
        business_id="business-2",
    ).values["business"]["profile"]["industry"] == "retail"
