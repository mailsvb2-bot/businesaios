from __future__ import annotations

from types import SimpleNamespace

from application.autonomy.autonomy_execution_step import (
    AutonomyExecutionStep,
    _v2_intent_mutation,
)
from contracts.decisioning.sovereign_decision_contract import Decision, DecisionContractV2
from core.security.keyring import Keyring
from kernel.decision_crypto import signed_envelope_from_decision


def _envelope(*, version: int = 2):
    payload = {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "goal_id": "goal-1",
        "user_id": "customer-1",
        "text": "original message",
        "estimated_cost": 3.5,
    }
    contract = None
    if version >= 2:
        contract = DecisionContractV2(
            business_id="business-1",
            goal_id="goal-1",
            world_state_version="semantic-state-1",
            agent_id="businesaios-core",
            model_profile="UNKNOWN",
            decision_strategy="policy-1",
            alternatives=None,
            selected_option={"option_id": "send_message@v1"},
            rationale={
                "evidence": [],
                "constraints": None,
                "alternatives": None,
                "selection_reason": "UNKNOWN",
                "uncertainties": ["alternatives:UNKNOWN"],
                "expected_outcome": None,
                "risk": None,
            },
            created_at=1000,
        ).as_dict()
    decision = Decision(
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
        envelope_version=version,
        contract_v2=contract,
    )
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    return signed_envelope_from_decision(decision=decision, keyring=keyring)


def _action(envelope, *, action_type: str | None = None, payload_patch: dict | None = None):
    payload = dict(envelope.decision.payload)
    payload.update(dict(payload_patch or {}))
    payload["capability_planning"] = {
        "allowed": True,
        "fallback_used": bool(action_type and action_type != envelope.decision.action),
    }
    return SimpleNamespace(
        action_type=action_type or envelope.decision.action,
        action_id=f"action:{envelope.decision.decision_id}",
        intent_id=f"intent:{envelope.decision.decision_id}",
        channel="headless",
        payload=payload,
        evidence_refs=(),
        derived_fact_ref="",
    )


def _request():
    return SimpleNamespace(
        meta={},
        autonomy_tier="supervised",
        approval_policy={},
        constraints={},
        economy={},
    )


def _policy():
    return SimpleNamespace(blocked_by_policy=False, approval_required=False)


def test_v2_action_change_requires_new_intent_before_runtime_guard() -> None:
    envelope = _envelope()
    action = _action(envelope, action_type="notify_owner")
    step = AutonomyExecutionStep(contract=SimpleNamespace())

    result = step.execute(
        request=_request(),
        executable_action=action,
        envelope=envelope,
        autonomy_decision=_policy(),
    )

    assert result.ok is False
    assert result.error == "immutable_action_intent_changed"
    assert result.output["attempted"] is False
    assert result.output["executed"] is False
    assert result.output["operator_required"] is True
    proof = result.output["immutable_action_intent"]
    assert proof["action_changed"] is True
    assert proof["reason"] == "action_type_changed_after_decision"
    assert proof["requires_new_intent"] is True


def test_v2_signed_parameter_change_requires_new_intent() -> None:
    envelope = _envelope()
    action = _action(envelope, payload_patch={"text": "forged message"})
    step = AutonomyExecutionStep(contract=SimpleNamespace())

    result = step.execute(
        request=_request(),
        executable_action=action,
        envelope=envelope,
        autonomy_decision=_policy(),
    )

    assert result.ok is False
    proof = result.output["immutable_action_intent"]
    assert proof["action_changed"] is False
    assert proof["reason"] == "signed_parameters_changed_after_decision"
    assert proof["changed_parameter_keys"] == ["text"]


def test_v2_additive_execution_metadata_does_not_mutate_signed_intent() -> None:
    envelope = _envelope()
    action = _action(
        envelope,
        payload_patch={
            "routing_explanation": {"reason": "healthy_route"},
            "capability_diagnostics": {"healthy": True},
        },
    )

    assert _v2_intent_mutation(envelope=envelope, executable_action=action) is None


def test_v1_retains_legacy_capability_fallback_semantics() -> None:
    envelope = _envelope(version=1)
    action = _action(envelope, action_type="notify_owner")

    assert _v2_intent_mutation(envelope=envelope, executable_action=action) is None
