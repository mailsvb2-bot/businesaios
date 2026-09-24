from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.decision_runtime.emission import project_decision_proposed_event
from application.decision_runtime.flow import build_payload
from application.evidence.evidence_persistence import EvidencePersistenceService
from core.ai.decision_core import project_action_intent
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from storage.evidence_store import InMemoryEvidenceStore


def _state(*, goal_id: str | None, canonical_goal_id: str | None = None):
    meta: dict[str, object] = {}
    if goal_id is not None:
        meta["goal_id"] = goal_id
    if canonical_goal_id is not None:
        meta["canonical_goal"] = {"goal": {"goal_id": canonical_goal_id}}
    return SimpleNamespace(meta=meta, economy={}, world_model_semantics=None)


def _payload(*, goal_id: str = "goal-1") -> dict:
    _tagged, payload = build_payload(
        state=_state(goal_id=goal_id, canonical_goal_id=goal_id),
        out=SimpleNamespace(payload={"expected_value": 25.0, "confidence": 0.8}),
        pinned_world_model_meta={},
        tenant_id="tenant-1",
        product_id=None,
        domain=None,
        product_version=None,
        actor_id=None,
    )
    return payload


def _intent(*, goal_id: str = "goal-1"):
    payload = _payload(goal_id=goal_id)
    return project_action_intent(
        decision_id="decision-1",
        correlation_id="correlation-1",
        decided_action_type="send_message",
        channel="headless",
        tenant_id="tenant-1",
        business_id="business-1",
        payload=payload,
    )


def test_canonical_goal_id_is_bound_into_signed_decision_payload_surface() -> None:
    payload = _payload()
    assert payload["goal_id"] == "goal-1"
    assert payload["meta"]["canonical_goal_id"] == "goal-1"

    intent = _intent()
    assert intent.goal_id == "goal-1"
    body = intent.as_dict()
    assert body["schema_version"] == 1
    assert body["payload"]["goal_id"] == "goal-1"
    assert body["payload"]["meta"]["canonical_goal_id"] == "goal-1"


def test_goal_identity_binding_is_noop_for_legacy_decisions_without_canonical_goal() -> None:
    _tagged, payload = build_payload(
        state=_state(goal_id=None),
        out=SimpleNamespace(payload={"expected_value": 25.0}),
        pinned_world_model_meta={},
        tenant_id="tenant-legacy",
        product_id=None,
        domain=None,
        product_version=None,
        actor_id=None,
    )
    assert "goal_id" not in payload
    assert "canonical_goal_id" not in dict(payload.get("meta") or {})

    intent = project_action_intent(
        decision_id="decision-legacy",
        correlation_id="correlation-legacy",
        decided_action_type="send_message",
        channel="headless",
        tenant_id="tenant-legacy",
        business_id="business-legacy",
        payload=payload,
    )
    assert intent.goal_id is None
    assert intent.schema_version == 1


def test_goal_identity_mismatch_fails_closed_before_decision_issuance() -> None:
    with pytest.raises(RuntimeError, match="DECISION_GOAL_ID_MISMATCH"):
        build_payload(
            state=_state(goal_id="goal-request", canonical_goal_id="goal-canonical"),
            out=SimpleNamespace(payload={}),
            pinned_world_model_meta={},
            tenant_id="tenant-1",
            product_id=None,
            domain=None,
            product_version=None,
            actor_id=None,
        )

    with pytest.raises(RuntimeError, match="DECISION_GOAL_ID_MISMATCH"):
        build_payload(
            state=_state(goal_id="goal-1", canonical_goal_id="goal-1"),
            out=SimpleNamespace(payload={"goal_id": "goal-forged"}),
            pinned_world_model_meta={},
            tenant_id="tenant-1",
            product_id=None,
            domain=None,
            product_version=None,
            actor_id=None,
        )


def test_goal_lineage_reaches_canonical_evidence_without_rewriting_intent_v1() -> None:
    intent = _intent()
    store = InMemoryEvidenceStore()
    EvidencePersistenceService(evidence_store=store).persist(
        tenant_id=intent.tenant_id,
        business_id=intent.business_id,
        run_id="run-1",
        goal="increase_profit",
        goal_id="goal-1",
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

    record = store.list_for_tenant(tenant_id=intent.tenant_id)[0]
    assert record.lineage["goal"] == "goal-1"
    assert record.lineage["decision"] == intent.decision_id
    assert record.labels["goal_id"] == "goal-1"


def test_evidence_rejects_conflicting_persisted_goal_vs_signed_intent_goal() -> None:
    intent = _intent(goal_id="goal-signed")
    store = InMemoryEvidenceStore()
    with pytest.raises(ValueError, match="canonical goal lineage conflicts"):
        EvidencePersistenceService(evidence_store=store).persist(
            tenant_id=intent.tenant_id,
            business_id=intent.business_id,
            run_id="run-conflict",
            goal="increase_profit",
            goal_id="goal-other",
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



def _decision_event(*, intent, issued_at_ms: int = 1000) -> dict:
    events = MemoryEventStore()
    decision = SimpleNamespace(
        decision_id=intent.decision_id,
        correlation_id=intent.correlation_id,
        action=intent.action_type,
        issued_at_ms=issued_at_ms,
        issuer_id="businesaios-core",
        policy_id="policy-test",
        snapshot_id="snapshot-test",
        state_hash="state-hash",
    )
    envelope = SimpleNamespace(decision=decision, payload_hash="decision-payload-hash")
    event_id = project_decision_proposed_event(
        event_store=events,
        envelope=envelope,
        action_intent=intent,
    )
    matches = [
        dict(row)
        for row in events.iter_events(
            tenant_id=intent.tenant_id,
            start_ms=0,
            event_type="decision.proposed",
        )
        if str(row.get("event_id") or "") == event_id
    ]
    assert len(matches) == 1
    return matches[0]


def test_decision_event_includes_goal_only_for_goal_bound_decisions() -> None:
    bound = _decision_event(intent=_intent())
    assert bound["payload"]["decision"]["goal_id"] == "goal-1"

    legacy_payload = build_payload(
        state=_state(goal_id=None),
        out=SimpleNamespace(payload={}),
        pinned_world_model_meta={},
        tenant_id="tenant-1",
        product_id=None,
        domain=None,
        product_version=None,
        actor_id=None,
    )[1]
    legacy_intent = project_action_intent(
        decision_id="decision-legacy-event",
        correlation_id="correlation-legacy-event",
        decided_action_type="send_message",
        channel="headless",
        tenant_id="tenant-1",
        business_id="business-1",
        payload=legacy_payload,
    )
    legacy = _decision_event(intent=legacy_intent, issued_at_ms=1001)
    assert "goal_id" not in legacy["payload"]["decision"]


def test_action_intent_rejects_conflicting_goal_identity_copies() -> None:
    payload = _payload()
    payload["goal_id"] = "goal-forged"
    with pytest.raises(ValueError, match="invalid:goal_id"):
        project_action_intent(
            decision_id="decision-conflict",
            correlation_id="correlation-conflict",
            decided_action_type="send_message",
            channel="headless",
            tenant_id="tenant-1",
            business_id="business-1",
            payload=payload,
        )
