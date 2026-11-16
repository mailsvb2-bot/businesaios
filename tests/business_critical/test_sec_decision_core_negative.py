"""Security regressions for DecisionCore business identity and signed payload integrity."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from contracts.action_intent import ActionIntentV1
from core.ai.decision_core import project_action_intent, project_action_intent_v2, project_executable_action
from core.utils.canonical import payload_hash
from execution.capability_aware_planning import CapabilityPlanDecision


def _decision(business_id: str = "biz-1") -> SimpleNamespace:
    return SimpleNamespace(
        decision_id="dec-v2",
        correlation_id="corr-v2",
        action="send_message",
        issuer_id="agent-1",
        payload={"estimated_cost": 1, "reversible": True},
        contract_v2={
            "schema_version": 2,
            "business_id": business_id,
            "goal_id": "goal-1",
            "agent_id": "agent-1",
            "expected_value": 10,
            "confidence": 0.5,
            "risk": "low",
        },
    )


def _v1() -> ActionIntentV1:
    return project_action_intent(
        decision_id="dec-1",
        correlation_id="corr-1",
        decided_action_type="send_message",
        channel="max",
        tenant_id="tenant-1",
        business_id="biz-1",
        payload={"estimated_cost": 1, "reversible": True},
    )


def _capability() -> CapabilityPlanDecision:
    return CapabilityPlanDecision(
        action_type="send_message",
        payload_patch={},
        allowed=True,
        fallback_used=False,
        reason="allowed",
        capability={"allowed": True},
    )


def test_v2_intent_is_bound_to_the_requested_business() -> None:
    decision = _decision("biz-1")
    intent = project_action_intent_v2(
        decision=decision,
        payload_hash=payload_hash(decision.payload),
        channel="max",
        tenant_id="tenant-1",
        business_id="biz-1",
    )
    assert (intent.tenant_id, intent.business_id) == ("tenant-1", "biz-1")


@pytest.mark.parametrize("requested", ["biz-2", "", "BIZ-1"])
def test_v2_intent_refuses_a_different_business_identity(requested: str) -> None:
    decision = _decision("biz-1")
    with pytest.raises(ValueError, match="business identity mismatch"):
        project_action_intent_v2(
            decision=decision,
            payload_hash=payload_hash(decision.payload),
            channel="max",
            tenant_id="tenant-1",
            business_id=requested,
        )


def test_issued_intent_with_tampered_hash_fails_before_executable_projection() -> None:
    intent = _v1()
    object.__setattr__(intent, "payload_hash", "b" * 64)
    with pytest.raises(ValueError, match="payload integrity check failed"):
        project_executable_action(
            decision_id=intent.decision_id,
            correlation_id=intent.correlation_id,
            decided_action_type=intent.action_type,
            channel=intent.channel,
            payload=intent.payload_copy(),
            capability_plan=_capability(),
            enforce_capability_plan=True,
            action_intent=intent,
        )


def test_untampered_intent_passes_the_same_executable_projection() -> None:
    intent = _v1()
    action = project_executable_action(
        decision_id=intent.decision_id,
        correlation_id=intent.correlation_id,
        decided_action_type=intent.action_type,
        channel=intent.channel,
        payload=intent.payload_copy(),
        capability_plan=_capability(),
        enforce_capability_plan=True,
        action_intent=intent,
    )
    assert dataclasses.is_dataclass(intent)
    assert action.intent_id == intent.intent_id
