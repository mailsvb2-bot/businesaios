from __future__ import annotations

from dataclasses import replace

import pytest

from application.evidence.evidence_persistence import EvidencePersistenceService
from application.outcome import (
    BusinessOutcomeEvaluationProjector,
    BusinessOutcomeProjectionConflict,
)
from contracts.business_outcome import BusinessOutcomeV1
from storage.evidence_store import InMemoryEvidenceStore


def _payloads() -> tuple[BusinessOutcomeV1, dict[str, object]]:
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id="tenant-14",
        business_id="business-14",
        run_id="run-14",
        intent_id="intent-14",
        decision_id="decision-14",
        action_id="action-14",
        action_type="send_email",
        goal="grow revenue",
        status="verified",
        feedback={
            "attempted": True,
            "executed": True,
            "verified": True,
            "verification_status": "verified",
            "goal_evaluation": {
                "achieved": True,
                "terminal": True,
                "completion_ratio": 1.0,
                "success_confidence": 0.99,
            },
            "revenue_outcome": {
                "revenue_amount": 250.0,
                "verified": True,
            },
            "normalized_outcome": {
                "margin": 80.0,
                "conversion_rate": 0.4,
                "retention_rate": 0.9,
                "actual_cost": 25.0,
                "latency_ms": 90.0,
                "complaint_count": 0.0,
                "human_override": False,
                "human_override_observed": True,
                "policy_violations": 0.0,
                "execution_failures": 0.0,
            },
            "execution_feedback": {"source_of_truth": "provider_receipt"},
            "external_refs": ["provider:receipt:14"],
        },
        evidence_refs=("evidence:world:14",),
        derived_fact_ref="fact:14",
    )
    intent: dict[str, object] = {
        "schema_version": 2,
        "action_id": outcome.action_id,
        "intent_id": outcome.intent_id,
        "tenant_id": outcome.tenant_id,
        "business_id": outcome.business_id,
        "decision_id": outcome.decision_id,
        "correlation_id": "correlation-14",
        "goal_id": "goal-14",
        "agent_id": "agent-14",
        "capability_target": outcome.action_type,
        "parameters": {},
        "expected_value": 300.0,
        "estimated_cost": 25.0,
        "confidence": 0.8,
        "channel": "email",
        "payload_hash": "0" * 64,
        "evidence_refs": ["evidence:world:14"],
        "derived_fact_ref": "fact:14",
    }
    return outcome, intent


def _persist(store: InMemoryEvidenceStore) -> None:
    outcome, intent = _payloads()
    EvidencePersistenceService(evidence_store=store).persist(
        tenant_id=outcome.tenant_id,
        business_id=outcome.business_id,
        run_id=outcome.run_id,
        goal=outcome.goal,
        goal_id="goal-14",
        step_index=0,
        action={
            "action_type": outcome.action_type,
            "action_id": outcome.action_id,
            "decision_id": outcome.decision_id,
            "derived_fact_ref": outcome.derived_fact_ref,
            "evidence_refs": list(outcome.evidence_refs),
        },
        execution_result={
            "executed": True,
            "source_of_truth": outcome.source_of_truth,
        },
        verification_result={
            "verified": True,
            "verification": {
                "status": "verified",
                "external_refs": list(outcome.external_refs),
            },
        },
        world_state_before={},
        world_state_after={},
        final_feedback={
            "business_outcome": outcome.as_dict(),
            "action_intent": intent,
        },
    )


def test_phase14_evaluation_and_calibration_are_bound_to_canonical_evidence() -> None:
    store = InMemoryEvidenceStore()
    _persist(store)

    record = store.list_for_tenant(tenant_id="tenant-14")[0]
    assert record.payload["evaluation"]["metrics"]["revenue"] == 250.0
    assert record.payload["evaluation"]["metrics"]["margin"] == 80.0
    assert record.payload["calibration_observation"] == {
        "schema_version": 1,
        "outcome_id": "outcome:action-14",
        "decision_id": "decision-14",
        "action_id": "action-14",
        "confidence": 0.8,
        "success": 1.0,
    }

    report = BusinessOutcomeEvaluationProjector(store).evaluate_business(
        tenant_id="tenant-14",
        business_id="business-14",
    )
    assert report.outcome_count == 1
    assert report.metric_means["revenue"] == 250.0
    assert report.metric_means["goal_completion"] == 1.0
    assert report.metric_coverage["human_override"] == 1.0
    assert report.calibration.sample_size == 1
    assert report.calibration.mean_confidence == 0.8
    assert report.calibration.observed_success_rate == 1.0


def test_phase14_legacy_evidence_replays_without_rewrite() -> None:
    source = InMemoryEvidenceStore()
    _persist(source)
    record = source.list_for_tenant(tenant_id="tenant-14")[0]
    payload = dict(record.payload)
    payload.pop("evaluation")
    payload.pop("calibration_observation")

    legacy = InMemoryEvidenceStore()
    legacy.append(replace(record, payload=payload))
    before = legacy.list_for_tenant(tenant_id="tenant-14")[0]

    _persist(legacy)

    after = legacy.list_for_tenant(tenant_id="tenant-14")[0]
    assert after == before
    assert "evaluation" not in after.payload
    assert "calibration_observation" not in after.payload

    report = BusinessOutcomeEvaluationProjector(legacy).evaluate_business(
        tenant_id="tenant-14",
        business_id="business-14",
    )
    assert report.outcome_count == 1
    assert report.metric_means["revenue"] == 250.0
    assert report.calibration.sample_size == 1


def test_phase14_projection_rejects_tampered_persisted_evaluation() -> None:
    source = InMemoryEvidenceStore()
    _persist(source)
    record = source.list_for_tenant(tenant_id="tenant-14")[0]
    payload = dict(record.payload)
    evaluation = dict(payload["evaluation"])
    metrics = dict(evaluation["metrics"])
    metrics["revenue"] = 999999.0
    evaluation["metrics"] = metrics
    payload["evaluation"] = evaluation

    tampered = InMemoryEvidenceStore()
    tampered.append(replace(record, payload=payload))

    with pytest.raises(
        BusinessOutcomeProjectionConflict,
        match="evaluation conflicts",
    ):
        BusinessOutcomeEvaluationProjector(tampered).evaluate_business(
            tenant_id="tenant-14",
            business_id="business-14",
        )


def test_phase14_projection_rejects_tampered_persisted_calibration() -> None:
    source = InMemoryEvidenceStore()
    _persist(source)
    record = source.list_for_tenant(tenant_id="tenant-14")[0]
    payload = dict(record.payload)
    calibration = dict(payload["calibration_observation"])
    calibration["confidence"] = 0.01
    payload["calibration_observation"] = calibration

    tampered = InMemoryEvidenceStore()
    tampered.append(replace(record, payload=payload))

    with pytest.raises(
        BusinessOutcomeProjectionConflict,
        match="calibration conflicts",
    ):
        BusinessOutcomeEvaluationProjector(tampered).evaluate_business(
            tenant_id="tenant-14",
            business_id="business-14",
        )
