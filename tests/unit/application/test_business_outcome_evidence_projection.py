from __future__ import annotations

from dataclasses import replace

import pytest

from application.evidence.evidence_persistence import EvidencePersistenceService
from application.outcome import (
    BusinessOutcomeEvidenceProjector,
    BusinessOutcomeProjectionConflict,
)
from contracts.business_outcome import BusinessOutcomeV1
from storage.evidence_store import EvidenceStore, InMemoryEvidenceStore, SqliteEvidenceStore
from storage.sqlite_fallback import SqliteSessionFactory


def _outcome() -> BusinessOutcomeV1:
    return BusinessOutcomeV1.from_feedback(
        tenant_id="tenant-1",
        business_id="business-1",
        run_id="run-1",
        intent_id="intent:decision-1",
        decision_id="decision-1",
        action_id="action-1",
        action_type="send_message",
        goal="reactivate_customer",
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
                "success_confidence": 0.91,
            },
            "revenue_outcome": {"revenue_amount": 1250.0, "verified": True},
            "normalized_outcome": {"converted": True},
            "execution_feedback": {"source_of_truth": "provider_receipt"},
            "external_refs": ["proof:provider-1"],
        },
        evidence_refs=("evidence-world-1",),
        derived_fact_ref="semantic-state-1",
    )


def _persist(store: EvidenceStore, outcome: BusinessOutcomeV1) -> None:
    EvidencePersistenceService(evidence_store=store).persist(
        tenant_id=outcome.tenant_id,
        business_id=outcome.business_id,
        run_id=outcome.run_id,
        goal=outcome.goal,
        step_index=0,
        action={
            "action_type": outcome.action_type,
            "action_id": outcome.action_id,
            "decision_id": outcome.decision_id,
            "derived_fact_ref": outcome.derived_fact_ref,
            "evidence_refs": list(outcome.evidence_refs),
        },
        execution_result={"executed": True, "source_of_truth": outcome.source_of_truth},
        verification_result={
            "verified": True,
            "verification": {"status": "verified", "external_refs": list(outcome.external_refs)},
        },
        world_state_before={},
        world_state_after={},
        final_feedback={"business_outcome": outcome.as_dict()},
    )


def test_canonical_evidence_round_trips_full_business_outcome() -> None:
    store = InMemoryEvidenceStore()
    expected = _outcome()
    _persist(store, expected)
    record = store.list_for_tenant(tenant_id=expected.tenant_id)[0]
    assert record.payload["business_outcome"] == expected.as_dict()
    projector = BusinessOutcomeEvidenceProjector(store)
    assert projector.get(
        tenant_id=expected.tenant_id,
        business_id=expected.business_id,
        outcome_id=expected.outcome_id,
    ) == expected
    assert projector.list_for_business(
        tenant_id=expected.tenant_id,
        business_id=expected.business_id,
    ) == (expected,)


def test_goal_id_is_bound_to_evidence_without_rewriting_business_outcome_schema() -> None:
    store = InMemoryEvidenceStore()
    expected = _outcome()
    artifacts = EvidencePersistenceService(evidence_store=store).persist(
        tenant_id=expected.tenant_id,
        business_id=expected.business_id,
        run_id=expected.run_id,
        goal=expected.goal,
        goal_id="goal-canonical",
        step_index=0,
        action={
            "action_type": expected.action_type,
            "action_id": expected.action_id,
            "decision_id": expected.decision_id,
            "derived_fact_ref": expected.derived_fact_ref,
            "evidence_refs": list(expected.evidence_refs),
        },
        execution_result={"executed": True, "source_of_truth": expected.source_of_truth},
        verification_result={
            "verified": True,
            "verification": {
                "status": "verified",
                "external_refs": list(expected.external_refs),
            },
        },
        world_state_before={},
        world_state_after={},
        final_feedback={"business_outcome": expected.as_dict()},
    )

    assert artifacts.outcome_record is not None
    assert artifacts.outcome_record["goal_id"] == "goal-canonical"
    record = store.list_for_tenant(tenant_id=expected.tenant_id)[0]
    assert record.labels["goal_id"] == "goal-canonical"
    assert record.payload["business_outcome"] == expected.as_dict()
    assert "goal_id" not in expected.as_dict()


def test_business_outcome_projection_is_scope_isolated() -> None:
    store = InMemoryEvidenceStore()
    expected = _outcome()
    _persist(store, expected)
    projector = BusinessOutcomeEvidenceProjector(store)
    with pytest.raises(LookupError):
        projector.get(tenant_id="tenant-other", business_id=expected.business_id, outcome_id=expected.outcome_id)
    with pytest.raises(LookupError):
        projector.get(tenant_id=expected.tenant_id, business_id="business-other", outcome_id=expected.outcome_id)


def test_legacy_outcome_lineage_without_full_body_is_retained_but_not_canonical() -> None:
    source = InMemoryEvidenceStore()
    expected = _outcome()
    _persist(source, expected)
    record = source.list_for_tenant(tenant_id=expected.tenant_id)[0]
    payload = dict(record.payload)
    payload.pop("business_outcome")
    legacy_store = InMemoryEvidenceStore()
    legacy_store.append(replace(record, payload=payload))
    projector = BusinessOutcomeEvidenceProjector(legacy_store)
    with pytest.raises(LookupError):
        projector.get(
            tenant_id=expected.tenant_id,
            business_id=expected.business_id,
            outcome_id=expected.outcome_id,
        )
    assert projector.list_for_business(
        tenant_id=expected.tenant_id, business_id=expected.business_id
    ) == ()
    assert projector.legacy_incomplete_count(
        tenant_id=expected.tenant_id, business_id=expected.business_id
    ) == 1


def test_tampered_business_outcome_body_conflicts_with_evidence_identity() -> None:
    source = InMemoryEvidenceStore()
    expected = _outcome()
    _persist(source, expected)
    record = source.list_for_tenant(tenant_id=expected.tenant_id)[0]
    payload = dict(record.payload)
    body = dict(payload["business_outcome"])
    body["decision_id"] = "decision-forged"
    payload["business_outcome"] = body
    tampered_store = InMemoryEvidenceStore()
    tampered_store.append(replace(record, payload=payload))
    with pytest.raises(BusinessOutcomeProjectionConflict):
        BusinessOutcomeEvidenceProjector(tampered_store).get(
            tenant_id=expected.tenant_id,
            business_id=expected.business_id,
            outcome_id=expected.outcome_id,
        )


def test_business_outcome_projection_survives_sqlite_restart(tmp_path) -> None:
    expected = _outcome()
    db_path = tmp_path / "business-outcomes.sqlite3"
    first_store = SqliteEvidenceStore(SqliteSessionFactory(db_path))
    _persist(first_store, expected)

    restarted_store = SqliteEvidenceStore(SqliteSessionFactory(db_path))
    assert BusinessOutcomeEvidenceProjector(restarted_store).get(
        tenant_id=expected.tenant_id,
        business_id=expected.business_id,
        outcome_id=expected.outcome_id,
    ) == expected
