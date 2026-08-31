from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.autonomy.autonomy_tiers import evaluate_autonomy_transition
from application.headless.decision_gateway import issue_headless_decision
from contracts import executable_action as executable_action_contract
from core.ai.decision_core import project_action_intent, project_executable_action
from execution.headless_trace import HeadlessTrace

CANON_AUTONOMY_DECISION_STEP = True
CANON_AUTONOMY_DELEGATES_EXECUTABLE_PROJECTION = True
CANON_AUTONOMY_PRESERVES_DECISION_RISK = True


@dataclass(frozen=True)
class DecisionStepArtifacts:
    envelope: Any
    explanation: Any
    action_intent: Any
    executable_action: executable_action_contract.ExecutableAction
    autonomy_decision: Any

    @property
    def policy_decision(self) -> Any:
        return self.autonomy_decision


class AutonomyDecisionStep:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract

    def evaluate(
        self,
        *,
        request: Any,
        state: Any,
        trace: HeadlessTrace,
        step_index: int,
        attempt_index: int,
    ) -> DecisionStepArtifacts:
        envelope = issue_headless_decision(decision_core=self._contract._decision_core, state=state)
        explanation = self._contract._policy_explainer.explain(state=state, envelope=envelope)
        action_intent = self._project_action_intent(request=request, envelope=envelope)
        trace.record(
            event_type="decision_issued",
            step_index=step_index,
            payload={
                "decision_id": envelope.decision.decision_id,
                "action": envelope.decision.action,
                "correlation_id": envelope.decision.correlation_id,
                "action_intent_id": action_intent.intent_id,
                "policy_explanation": {
                    "policy_id": explanation.policy_id,
                    "summary": explanation.summary,
                    "factors": list(explanation.factors),
                },
                "attempt_index": attempt_index,
            },
        )
        executable_action = self._project_executable_action(
            request=request, state=state, envelope=envelope, action_intent=action_intent,
        )
        autonomy_decision = evaluate_autonomy_transition(
            decided_action_type=action_intent.action_type,
            executable_action_type=str(executable_action.action_type),
            autonomy_tier=request.autonomy_tier,
            approval_policy=dict(request.approval_policy or {}),
        ).bind_intent(action_intent)
        return DecisionStepArtifacts(
            envelope=envelope, explanation=explanation, action_intent=action_intent,
            executable_action=executable_action, autonomy_decision=autonomy_decision,
        )

    decide = evaluate

    def _project_action_intent(self, *, request: Any, envelope: Any) -> Any:
        payload = self._intent_payload(request=request, envelope=envelope)
        return project_action_intent(
            decision_id=str(envelope.decision.decision_id),
            correlation_id=str(envelope.decision.correlation_id or ""),
            decided_action_type=str(envelope.decision.action),
            channel=str(request.channel), tenant_id=str(getattr(request, "tenant_id", "") or ""),
            business_id=str(getattr(request, "business_id", "") or ""), payload=payload,
            requested_by=str(getattr(envelope.decision, "issuer_id", "decision_core") or "decision_core"),
        )

    @staticmethod
    def _intent_payload(*, request: Any, envelope: Any) -> dict[str, Any]:
        payload = dict(envelope.decision.payload or {})
        payload.setdefault("tenant_id", str(getattr(request, "tenant_id", "") or ""))
        payload.setdefault("business_id", str(getattr(request, "business_id", "") or ""))
        payload.setdefault("user_id", str(getattr(request, "user_id", "") or ""))
        payload.setdefault(
            "autonomy_tier",
            str(getattr(request, "autonomy_tier", "supervised") or "supervised"),
        )
        payload.setdefault("approval_policy", dict(getattr(request, "approval_policy", {}) or {}))
        payload.setdefault("constraints", dict(getattr(request, "constraints", {}) or {}))
        payload.setdefault("economy", dict(getattr(request, "economy", {}) or {}))
        payload.setdefault("goal_plan", dict(getattr(request, "meta", {}).get("goal_plan") or {}))
        payload.setdefault(
            "previous_feedback",
            dict(getattr(request, "meta", {}).get("previous_feedback") or {}),
        )
        return payload

    def _project_executable_action(
        self, *, request: Any, state: Any, envelope: Any, action_intent: Any | None = None,
    ) -> executable_action_contract.ExecutableAction:
        action_intent = action_intent or self._project_action_intent(request=request, envelope=envelope)
        payload = action_intent.payload_copy()
        action_type = str(action_intent.action_type)
        capability_plan = self._contract._capability_aware_planner.plan_action(
            request=request,
            state=state,
            action_type=action_type,
            payload=payload,
        )
        return project_executable_action(
            decision_id=action_intent.decision_id,
            correlation_id=action_intent.correlation_id,
            decided_action_type=action_type,
            channel=str(request.channel),
            payload=payload,
            capability_plan=capability_plan,
            enforce_capability_plan=self._should_enforce_capability_plan(),
            action_intent=action_intent,
        )

    def _should_enforce_capability_plan(self) -> bool:
        executor = getattr(self._contract, "_executor", None)
        if executor is None:
            return False
        module_name = str(getattr(type(executor), "__module__", "") or "")
        if module_name.startswith("runtime."):
            return True
        return bool(getattr(executor, "enforce_capability_planning", False))


__all__ = [
    "CANON_AUTONOMY_DECISION_STEP",
    "CANON_AUTONOMY_DELEGATES_EXECUTABLE_PROJECTION",
    "CANON_AUTONOMY_PRESERVES_DECISION_RISK",
    "AutonomyDecisionStep",
    "DecisionStepArtifacts",
]
