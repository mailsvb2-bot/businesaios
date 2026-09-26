from __future__ import annotations

from dataclasses import replace

import pytest

from application.action import (
    ActionIntentEvidenceProjector,
    ActionIntentProjectionConflict,
)
from application.evidence.evidence_persistence import EvidencePersistenceService
from contracts.action_intent import ActionIntentV1
from core.ai.decision_core import project_action_intent
from storage.evidence_store import EvidenceStore, InMemoryEvidenceStore, SqliteEvidenceStore
from storage.sqlite_fallback import SqliteSessionFactory


def _intent() -> ActionIntentV1:
    return project_action_intent(
        decision_id="decision-1",
        correlation_id="correlation-1",
        decided_action_type="send_message",
        channel="max",
        tenant_id="tenant-1",
        business_id="business-1",
        payload={
            "recipient": {"id": "customer-1"},
            "estimated_cost": 3.5,
            "expected_value": 50.0,
            "confidence": 0.8,
            "reversible": True,
            "meta": {
                "world_model_meta": {
                    "semantic_state_id": "semantic-state-1",
                    "evidence_refs": ["evidence-world-1"],
                }
            },
        },
    )


def _persist(store: EvidenceStore, intent: ActionIntentV1) -> None:
    EvidencePersistenceService(evidence_store=store).persist(
        tenant_id=intent.tenant_id,
        business_id=intent.business_id,
        run_id="run-1",
        goal="reactivate_customer",
        step_index=0,
        action={
            "action_type": intent.action_type,
            "action_id": f"action:{intent.decision_id}",
            "decision_id": intent.decision_id,
        },
        execution_result={"executed": True},
        verification_result={"verified": True, "verification": {"status": "verified"}},
        world_state_before={},
        world_state_after={},
        final_feedback={"action_intent": intent.as_dict()},
    )


def test_canonical_evidence_round_trips_full_action_intent() -> None:
    store = InMemoryEvidenceStore()
    expected = _intent()
    _persist(store, expected)
    record = store.list_for_tenant(tenant_id=expected.tenant_id)[0]
    assert record.payload["action_intent"] == expected.as_dict()
    assert record.lineage["decision"] == expected.decision_id
    assert record.lineage["derived_fact"] == expected.derived_fact_ref
    assert expected.evidence_refs[0] in record.refs
    projector = ActionIntentEvidenceProjector(store)
    assert projector.get(
        tenant_id=expected.tenant_id,
        business_id=expected.business_id,
        intent_id=expected.intent_id,
    ) == expected


def test_action_intent_projection_survives_sqlite_restart(tmp_path) -> None:
    expected = _intent()
    db_path = tmp_path / "action-intents.sqlite3"
    first_store = SqliteEvidenceStore(SqliteSessionFactory(db_path))
    _persist(first_store, expected)

    restarted_store = SqliteEvidenceStore(SqliteSessionFactory(db_path))
    assert ActionIntentEvidenceProjector(restarted_store).get(
        tenant_id=expected.tenant_id,
        business_id=expected.business_id,
        intent_id=expected.intent_id,
    ) == expected


def test_action_intent_projection_is_scope_isolated() -> None:
    store = InMemoryEvidenceStore()
    expected = _intent()
    _persist(store, expected)
    projector = ActionIntentEvidenceProjector(store)
    with pytest.raises(LookupError):
        projector.get(
            tenant_id="tenant-other",
            business_id=expected.business_id,
            intent_id=expected.intent_id,
        )

    with pytest.raises(LookupError):
        projector.get(
            tenant_id=expected.tenant_id,
            business_id="business-other",
            intent_id=expected.intent_id,
        )


def test_legacy_closed_loop_row_without_intent_body_is_retained_but_not_canonical() -> None:
    source = InMemoryEvidenceStore()
    expected = _intent()
    _persist(source, expected)
    record = source.list_for_tenant(tenant_id=expected.tenant_id)[0]
    payload = dict(record.payload)
    payload.pop("action_intent")
    legacy = InMemoryEvidenceStore()
    legacy.append(replace(record, payload=payload))
    projector = ActionIntentEvidenceProjector(legacy)
    with pytest.raises(LookupError):
        projector.get(
            tenant_id=expected.tenant_id,
            business_id=expected.business_id,
            intent_id=expected.intent_id,
        )
    assert projector.list_for_business(
        tenant_id=expected.tenant_id, business_id=expected.business_id
    ) == ()
    assert projector.legacy_incomplete_count(
        tenant_id=expected.tenant_id, business_id=expected.business_id
    ) == 1


def test_tampered_action_intent_body_conflicts_with_evidence_identity() -> None:
    source = InMemoryEvidenceStore()
    expected = _intent()
    _persist(source, expected)
    record = source.list_for_tenant(tenant_id=expected.tenant_id)[0]
    payload = dict(record.payload)
    body = dict(payload["action_intent"])
    body["decision_id"] = "decision-forged"
    payload["action_intent"] = body
    tampered = InMemoryEvidenceStore()
    tampered.append(replace(record, payload=payload))
    with pytest.raises(ActionIntentProjectionConflict):
        ActionIntentEvidenceProjector(tampered).get(
            tenant_id=expected.tenant_id,
            business_id=expected.business_id,
            intent_id=expected.intent_id,
        )

def test_action_intent_carries_canonical_agent_identity() -> None:
    intent = project_action_intent(
        decision_id="decision-agent",
        correlation_id="correlation-agent",
        decided_action_type="send_message",
        channel="max",
        tenant_id="tenant-1",
        business_id="business-1",
        payload={},
        requested_by="business-agent",
        agent_id="business-agent",
    )
    assert intent.agent_id == "business-agent"
    assert intent.as_dict()["agent_id"] == "business-agent"
