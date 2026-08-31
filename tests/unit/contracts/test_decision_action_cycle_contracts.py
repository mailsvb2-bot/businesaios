from __future__ import annotations

from math import nan

import pytest

from application.autonomy.autonomy_tiers import AutonomyDecision, evaluate_autonomy_transition
from contracts.action_intent import ActionIntentV1
from contracts.business_outcome import BusinessOutcomeV1
from contracts.policy_decision import PolicyDecisionV1
from core.ai.decision_core import project_action_intent, project_executable_action
from execution.capability_aware_planning import CapabilityPlanDecision


def _intent(**overrides) -> ActionIntentV1:
    data = {
        "decision_id": "dec-1", "correlation_id": "corr-1", "decided_action_type": "send_message",
        "channel": "max", "tenant_id": "tenant-1", "business_id": "business-1",
        "payload": {"estimated_cost": 12, "expected_value": 900, "confidence": 0.8, "reversible": True},
    }
    data.update(overrides)
    return project_action_intent(**data)


def _capability(action_type: str = "send_message") -> CapabilityPlanDecision:
    return CapabilityPlanDecision(
        action_type=action_type, payload_patch={}, allowed=True, fallback_used=False, reason="allowed", capability={"allowed": True}
    )


def test_action_intent_is_non_effectful_identity_between_decision_and_execution() -> None:
    intent = _intent()
    action = project_executable_action(
        decision_id=intent.decision_id, correlation_id=intent.correlation_id, decided_action_type=intent.action_type,
        channel=intent.channel, payload=intent.payload, capability_plan=_capability(), enforce_capability_plan=True, action_intent=intent,
    )
    assert intent.intent_id == "intent:dec-1"
    assert intent.tenant_id == "tenant-1" and intent.business_id == "business-1"
    assert action.intent_id == intent.intent_id
    assert action.decision_id == intent.decision_id
    assert action.action_type == intent.action_type


def test_policy_decision_is_canonical_owner_and_binds_intent_identity() -> None:
    intent = _intent()
    decision = evaluate_autonomy_transition(
        decided_action_type=intent.action_type, executable_action_type=intent.action_type,
        autonomy_tier="supervised", approval_policy={},
    ).bind_intent(intent)
    assert AutonomyDecision is PolicyDecisionV1
    assert isinstance(decision, PolicyDecisionV1)
    assert decision.intent_id == intent.intent_id and decision.decision_id == intent.decision_id
    assert decision.tenant_id == intent.tenant_id and decision.business_id == intent.business_id
    assert decision.verdict in {"allowed", "approval_required", "denied", "not_authorized"}


def test_action_intent_economic_fields_fail_closed() -> None:
    with pytest.raises(ValueError, match="estimated_cost must be finite"):
        _intent(payload={"estimated_cost": nan})
    with pytest.raises(ValueError, match="invalid action intent projection: invalid:confidence"):
        _intent(payload={"confidence": 1.5})
    with pytest.raises(ValueError, match="invalid action intent projection: invalid:estimated_cost"):
        _intent(payload={"estimated_cost": -1})


def test_executable_projection_rejects_mismatched_intent_identity() -> None:
    intent = _intent()
    with pytest.raises(ValueError, match="action intent identity does not match executable projection"):
        project_executable_action(
            decision_id="dec-other", correlation_id=intent.correlation_id, decided_action_type=intent.action_type,
            channel=intent.channel, payload=intent.payload, capability_plan=_capability(), enforce_capability_plan=True, action_intent=intent,
        )


def test_business_outcome_binds_action_to_goal_and_economic_evidence() -> None:
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id="tenant-1", business_id="business-1", run_id="run-1", intent_id="intent:dec-1",
        decision_id="dec-1", action_id="action:dec-1", action_type="send_message", goal="reactivate_customer", status="verified",
        feedback={
            "attempted": True, "executed": True, "verified": True, "verification_status": "verified",
            "goal_evaluation": {"achieved": True, "terminal": True, "completion_ratio": 1.0, "success_confidence": 0.93},
            "revenue_outcome": {"revenue_amount": 12000, "verified": True},
            "normalized_outcome": {"converted": True, "revenue": 12000},
            "execution_feedback": {"source_of_truth": "provider_receipt"}, "external_refs": ["proof://payment-1"],
        },
    )
    assert outcome.outcome_id == "outcome:action:dec-1"
    assert outcome.intent_id == "intent:dec-1" and outcome.decision_id == "dec-1"
    assert outcome.goal_achieved is True and outcome.verified is True
    assert outcome.revenue_amount == 12000.0 and outcome.revenue_verified is True
    assert outcome.metrics["converted"] is True


def test_business_outcome_excludes_nonfinite_revenue() -> None:
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id="tenant-1", business_id="business-1", run_id="run-1", intent_id="intent:dec-1",
        decision_id="dec-1", action_id="action:dec-1", action_type="send_message", goal="goal", status="executed",
        feedback={"revenue_outcome": {"revenue_amount": float("nan")}},
    )
    assert outcome.revenue_amount is None
