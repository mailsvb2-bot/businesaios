from __future__ import annotations

from contracts.action_intent import ActionIntentV2
from contracts.decisioning.sovereign_decision_contract import Decision, DecisionContractV2
from core.utils.canonical import payload_hash


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
