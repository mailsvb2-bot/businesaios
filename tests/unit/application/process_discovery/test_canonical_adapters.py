from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from application.process_discovery import BuildRequest, DiscoverBuildMeasureService, DiscoveryPolicy
from application.process_discovery.canonical_adapters import (
    CanonicalBlueprintLedger,
    CanonicalProcessEvidenceStore,
    CanonicalProcessMeasurementSource,
)
from observability.platform.telemetry.event_store import InMemoryEventStore
from storage.evidence_store import InMemoryEvidenceStore

BASE = datetime(2026, 9, 1, tzinfo=UTC)


def _owner_payload(*, day: int, process_key: str = "follow_up") -> dict:
    return {
        "process_key": process_key,
        "occurred_at": (BASE + timedelta(days=day)).isoformat(),
        "manual_minutes": 40,
        "actor_cost_per_hour_minor": 50_000,
        "direct_loss_minor": 1_000,
        "revenue_at_risk_minor": 5_000,
        "currency": "RUB",
        "automation_fit": 0.9,
        "operational_risk": 0.1,
    }


def _built(store: InMemoryEventStore):
    evidence = CanonicalProcessEvidenceStore(store, InMemoryEvidenceStore())
    for day in range(6):
        evidence.record_owner_observation(
            tenant_id="t1", business_id="b1", user_id="owner-1", payload=_owner_payload(day=day)
        )
    service = DiscoverBuildMeasureService(
        DiscoveryPolicy(min_observations=5, min_window_days=5, min_confidence=0.2)
    )
    opportunity = service.discover(evidence.load_process_observations(tenant_id="t1", business_id="b1")).opportunities[0]
    blueprint = service.build(opportunity, BuildRequest(owner_goal="Сократить ручной follow-up"))
    return evidence, opportunity, blueprint


def test_owner_observation_is_server_identified_and_owner_money_is_not_verified() -> None:
    store = InMemoryEventStore()
    evidence = CanonicalProcessEvidenceStore(store, InMemoryEvidenceStore())
    item = evidence.record_owner_observation(
        tenant_id="t1",
        business_id="b1",
        user_id="owner-1",
        payload={**_owner_payload(day=0), "evidence_id": "browser-id", "source": "crm", "trust_weight": 1.0},
    )
    assert item.evidence_id.startswith("pev_")
    assert item.evidence_id != "browser-id"
    assert item.source == "owner_asserted"
    assert item.trust_weight == 0.65

    for day in range(1, 6):
        evidence.record_owner_observation(
            tenant_id="t1", business_id="b1", user_id="owner-1", payload=_owner_payload(day=day)
        )
    report = DiscoverBuildMeasureService(
        DiscoveryPolicy(min_observations=5, min_window_days=5, min_confidence=0.2)
    ).discover(evidence.load_process_observations(tenant_id="t1", business_id="b1"))
    candidate = report.opportunities[0]
    assert candidate.baseline.money_status.value == "partial"
    assert candidate.baseline.realized_loss_minor_per_30d is None


def test_blueprint_ledger_roundtrips_without_creating_a_second_store() -> None:
    store = InMemoryEventStore()
    _, opportunity, blueprint = _built(store)
    ledger = CanonicalBlueprintLedger(store)
    ledger.save(blueprint=blueprint, baseline=opportunity.baseline)
    loaded = ledger.get(tenant_id="t1", business_id="b1", blueprint_id=blueprint.blueprint_id)
    assert loaded is not None
    assert loaded[0] == blueprint
    assert loaded[1] == opportunity.baseline
    ledger.save(blueprint=blueprint, baseline=opportunity.baseline)


def test_direct_verified_decision_step_becomes_intervention_proof() -> None:
    store = InMemoryEventStore()
    evidence, opportunity, blueprint = _built(store)
    source = CanonicalProcessMeasurementSource(event_store=store, evidence_source=evidence)
    source.record_decision_result(
        tenant_id="t1",
        business_id="b1",
        blueprint=blueprint,
        result={
            "run_id": "run-1",
            "trace_id": "trace-1",
            "completed": True,
            "stop_reason": "done",
            "steps": [{"step_index": 0, "decision_id": "d1", "action_id": "a1", "action": "internal@v1", "executed": True, "verified": True}],
        },
    )
    proof = source.load_intervention_proof(tenant_id="t1", business_id="b1", blueprint=blueprint)
    assert proof is not None
    assert proof.server_validated is True
    assert proof.execution_verified is True
    assert proof.run_id == "run-1"
    assert proof.decision_id == "d1"
    assert proof.action_id == "a1"
    assert proof.started_at > opportunity.baseline.window_end


def test_whatsapp_provider_acceptance_without_delivery_is_not_intervention_proof() -> None:
    store = InMemoryEventStore()
    evidence, _, blueprint = _built(store)

    def history_reader(**kwargs):
        if kwargs["provider_key"] != "whatsapp_cloud":
            return ()
        return ({
            "status": "live_executed",
            "accepted": True,
            "recorded_at_utc": (BASE + timedelta(days=10)).isoformat(),
            "queue_job_id": "job-wa",
            "parsed_response": {"resource_id": "wamid-1", "delivery_state": "accepted"},
            "decision_provenance": {
                "run_id": "run-wa", "decision_id": "d-wa", "action_id": "a-wa",
                "tenant_id": "t1", "business_id": "b1",
            },
        },)

    source = CanonicalProcessMeasurementSource(store, evidence, history_reader)
    source.record_decision_result(
        tenant_id="t1", business_id="b1", blueprint=blueprint,
        result={"run_id": "run-wa", "steps": [{"decision_id": "d-wa", "action_id": "a-wa", "action": "send_message@v1", "executed": False, "verified": False}]},
    )
    assert source.load_intervention_proof(tenant_id="t1", business_id="b1", blueprint=blueprint) is None


def test_provider_delivery_uses_same_canonical_delivery_truth_as_action_center() -> None:
    store = InMemoryEventStore()
    evidence, _, blueprint = _built(store)

    def history_reader(**kwargs):
        if kwargs["provider_key"] != "telegram_bot":
            return ()
        return ({
            "status": "live_executed",
            "accepted": True,
            "recorded_at_utc": (BASE + timedelta(days=10)).isoformat(),
            "queue_job_id": "job-tg",
            "parsed_response": {"resource_id": "42", "delivery_state": "accepted"},
            "decision_provenance": {
                "run_id": "run-tg", "decision_id": "d-tg", "action_id": "a-tg",
                "tenant_id": "t1", "business_id": "b1",
            },
        },)

    source = CanonicalProcessMeasurementSource(store, evidence, history_reader)
    source.record_decision_result(
        tenant_id="t1", business_id="b1", blueprint=blueprint,
        result={"run_id": "run-tg", "steps": [{"decision_id": "d-tg", "action_id": "a-tg", "action": "send_message@v1", "executed": False, "verified": False}]},
    )
    proof = source.load_intervention_proof(tenant_id="t1", business_id="b1", blueprint=blueprint)
    assert proof is not None
    assert proof.intervention_id == "provider:telegram_bot:job-tg"
    assert "42" in proof.evidence_refs


def test_future_owner_observation_is_rejected() -> None:
    store = InMemoryEventStore()
    evidence = CanonicalProcessEvidenceStore(store, InMemoryEvidenceStore())
    with pytest.raises(ValueError, match="occurred_at_in_future"):
        evidence.record_owner_observation(
            tenant_id="t1", business_id="b1", user_id="owner-1",
            payload={**_owner_payload(day=0), "occurred_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        )


def test_owner_process_observation_is_backed_by_canonical_evidence_and_replay_is_idempotent() -> None:
    event_store = InMemoryEventStore()
    canonical = InMemoryEvidenceStore()
    evidence = CanonicalProcessEvidenceStore(event_store, canonical)
    payload = _owner_payload(day=0)

    first = evidence.record_owner_observation(
        tenant_id="t1", business_id="b1", user_id="owner-1", payload=payload, request_id="req-1"
    )
    second = evidence.record_owner_observation(
        tenant_id="t1", business_id="b1", user_id="owner-1", payload=payload, request_id="req-1"
    )

    assert first.evidence_id == second.evidence_id
    records = canonical.list_for_tenant(tenant_id="t1")
    assert len(records) == 1
    record = records[0]
    assert record.evidence_id == first.evidence_id
    assert record.business_id == "b1"
    assert record.source == "owner_asserted"
    assert record.source_type == "owner_process_observation"
    assert record.observed_at == first.occurred_at
    assert record.confidence == 0.65
    assert record.payload["process_key"] == first.process_key

    with pytest.raises(ValueError, match="replay conflicts with canonical evidence"):
        evidence.record_owner_observation(
            tenant_id="t1",
            business_id="b1",
            user_id="owner-1",
            payload={**payload, "manual_minutes": 999},
            request_id="req-1",
        )
