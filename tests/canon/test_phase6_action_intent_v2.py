from __future__ import annotations

from application.action import ActionIntentEvidenceProjector
from application.autonomy.autonomy_decision_step import AutonomyDecisionStep
from application.evidence.evidence_persistence import EvidencePersistenceService
from contracts.action_intent import ActionIntentV1, ActionIntentV2
from contracts.decisioning.sovereign_decision_contract import Decision, DecisionContractV2
from contracts.policy_decision import PolicyDecisionV1
from core.security.keyring import Keyring
from core.utils.canonical import payload_hash
from kernel.decision_crypto import signed_envelope_from_decision
from storage.evidence_store import InMemoryEvidenceStore


def _decision(*, goal_id: str | None = "goal-1", agent_id: str = "businesaios-core") -> Decision:
    payload = {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "autonomy_tier": "supervised",
        "estimated_cost": 3.5,
        "reversible": True,
        "deadline": "2026-10-01T12:00:00Z",
        "recipient": {"id": "customer-1"},
    }
    contract = DecisionContractV2(
        business_id="business-1",
        goal_id=goal_id,
        world_state_version="semantic-state-1",
        agent_id=agent_id,
        model_profile="model-1",
        decision_strategy="policy-1",
        alternatives=(
            {"option_id": "send_message@v1", "score": 3.0, "reason": "ranked"},
        ),
        selected_option={"option_id": "send_message@v1", "score": 3.0},
        rationale={
            "evidence": ["evidence-1"],
            "constraints": None,
            "alternatives": ["send_message@v1"],
            "selection_reason": "ranked",
            "uncertainties": [],
            "expected_outcome": None,
            "risk": {"level": "low"},
        },
        confidence=0.8,
        expected_value=25.0,
        risk={"level": "low"},
        created_at=1000,
        do_nothing_baseline=None,
    ).as_dict()
    return Decision(
        decision_id="decision-1",
        issuer_id="businesaios-core",
        issued_at_ms=1000,
        expires_at_ms=2000,
        policy_id="policy-1",
        action="send_message@v1",
        payload=payload,
        snapshot_id="snapshot-1",
        state_hash="state-hash",
        correlation_id="correlation-1",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=2,
        contract_v2=contract,
    )


def test_action_intent_v2_projects_signed_decision_economics_and_goal_identity() -> None:
    decision = _decision()
    intent = ActionIntentV2.from_decision(
        decision=decision,
        tenant_id="tenant-1",
        channel="headless",
        payload_hash=payload_hash(decision.payload),
        evidence_refs=("evidence-1",),
        derived_fact_ref="semantic-state-1",
    )

    assert intent.schema_version == 2
    assert intent.action_id == "action:decision-1"
    assert intent.intent_id == "intent:decision-1"
    assert intent.business_id == "business-1"
    assert intent.goal_id == "goal-1"
    assert intent.agent_id == "businesaios-core"
    assert intent.capability_target == "send_message@v1"
    assert intent.expected_value == 25.0
    assert intent.estimated_cost == 3.5
    assert intent.confidence == 0.8
    assert intent.risk == {"level": "low"}
    assert intent.reversibility is True
    assert intent.requested_autonomy == "supervised"
    assert intent.deadline == "2026-10-01T12:00:00Z"
    assert intent.parameters_copy()["recipient"]["id"] == "customer-1"
    assert intent.validate_contract() == []


def test_action_intent_v2_rejects_decision_agent_identity_drift() -> None:
    decision = _decision(agent_id="other-agent")
    try:
        ActionIntentV2.from_decision(
            decision=decision,
            tenant_id="tenant-1",
            channel="headless",
            payload_hash=payload_hash(decision.payload),
        )
    except ValueError as exc:
        assert "agent identity mismatch" in str(exc)
    else:
        raise AssertionError("agent identity drift must fail closed")


def test_action_intent_v2_requires_goal_identity() -> None:
    decision = _decision(goal_id=None)
    try:
        ActionIntentV2.from_decision(
            decision=decision,
            tenant_id="tenant-1",
            channel="headless",
            payload_hash=payload_hash(decision.payload),
        )
    except ValueError as exc:
        assert "invalid:goal_id" in str(exc)
    else:
        raise AssertionError("ActionIntent v2 without goal_id must fail closed")



def test_action_intent_v2_round_trips_through_canonical_evidence() -> None:
    decision = _decision()
    intent = ActionIntentV2.from_decision(
        decision=decision,
        tenant_id="tenant-1",
        channel="headless",
        payload_hash=payload_hash(decision.payload),
        evidence_refs=("evidence-1",),
        derived_fact_ref="semantic-state-1",
    )
    store = InMemoryEvidenceStore()
    EvidencePersistenceService(evidence_store=store).persist(
        tenant_id=intent.tenant_id,
        business_id=intent.business_id,
        run_id="run-v2",
        goal="increase_profit",
        goal_id=intent.goal_id,
        step_index=0,
        action={
            "action_type": intent.action_type,
            "action_id": intent.action_id,
            "decision_id": intent.decision_id,
            "derived_fact_ref": intent.derived_fact_ref,
            "evidence_refs": list(intent.evidence_refs),
        },
        execution_result={"executed": True},
        verification_result={"verified": True, "verification": {"status": "verified"}},
        world_state_before={},
        world_state_after={},
        final_feedback={"action_intent": intent.as_dict()},
    )

    record = store.list_for_tenant(tenant_id=intent.tenant_id)[0]
    assert record.labels["goal_id"] == "goal-1"
    assert record.payload["action_intent"]["schema_version"] == 2
    assert ActionIntentEvidenceProjector(store).get(
        tenant_id=intent.tenant_id,
        business_id=intent.business_id,
        intent_id=intent.intent_id,
    ) == intent


def test_action_intent_v2_evidence_rejects_goal_identity_conflict() -> None:
    decision = _decision()
    intent = ActionIntentV2.from_decision(
        decision=decision,
        tenant_id="tenant-1",
        channel="headless",
        payload_hash=payload_hash(decision.payload),
    )
    store = InMemoryEvidenceStore()
    try:
        EvidencePersistenceService(evidence_store=store).persist(
            tenant_id=intent.tenant_id,
            business_id=intent.business_id,
            run_id="run-v2-conflict",
            goal="increase_profit",
            goal_id="goal-forged",
            step_index=0,
            action={
                "action_type": intent.action_type,
                "action_id": intent.action_id,
                "decision_id": intent.decision_id,
            },
            execution_result={"executed": True},
            verification_result={"verified": True, "verification": {"status": "verified"}},
            world_state_before={},
            world_state_after={},
            final_feedback={"action_intent": intent.as_dict()},
        )
    except ValueError as exc:
        assert "canonical goal lineage conflicts" in str(exc)
    else:
        raise AssertionError("persisted Goal must match ActionIntent v2 goal_id")



class _Request:
    tenant_id = "tenant-1"
    business_id = "business-1"
    user_id = "user-1"
    autonomy_tier = "supervised"
    channel = "headless"
    approval_policy: dict = {}
    constraints: dict = {}
    economy: dict = {}
    meta: dict = {}


def test_autonomy_step_projects_v2_only_for_envelope_v2() -> None:
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    decision_v2 = _decision()
    envelope_v2 = signed_envelope_from_decision(decision=decision_v2, keyring=keyring)
    step = AutonomyDecisionStep(contract=object())

    intent_v2 = step._project_action_intent(request=_Request(), envelope=envelope_v2)
    assert isinstance(intent_v2, ActionIntentV2)
    assert intent_v2.goal_id == "goal-1"
    assert intent_v2.business_id == "business-1"

    decision_v1 = Decision(
        decision_id="decision-v1",
        issuer_id="businesaios-core",
        issued_at_ms=1000,
        expires_at_ms=2000,
        policy_id="policy-1",
        action="send_message@v1",
        payload={"tenant_id": "tenant-1", "business_id": "business-1"},
        snapshot_id="snapshot-v1",
        state_hash="state-v1",
        correlation_id="correlation-v1",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    envelope_v1 = signed_envelope_from_decision(decision=decision_v1, keyring=keyring)
    intent_v1 = step._project_action_intent(request=_Request(), envelope=envelope_v1)
    assert isinstance(intent_v1, ActionIntentV1)
    assert intent_v1.schema_version == 1



def test_policy_decision_v1_binds_action_intent_v2_identity_explicitly() -> None:
    decision = _decision()
    intent = ActionIntentV2.from_decision(
        decision=decision,
        tenant_id="tenant-1",
        channel="headless",
        payload_hash=payload_hash(decision.payload),
    )
    policy = PolicyDecisionV1(
        tier="supervised",
        action_type=intent.action_type,
        action_class="communications_write",
        allowed=True,
        approval_required=False,
        blocked_by_policy=False,
    ).bind_intent(intent)

    assert policy.intent_id == intent.intent_id
    assert policy.decision_id == intent.decision_id
    assert policy.tenant_id == intent.tenant_id
    assert policy.business_id == intent.business_id
    assert policy.verdict == "allowed"
