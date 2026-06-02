from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.autonomy.autonomy_tiers import evaluate_autonomy_tier
from application.headless.decision_gateway import issue_headless_decision
from contracts import executable_action as executable_action_contract
from execution.headless_trace import HeadlessTrace

CANON_AUTONOMY_DECISION_STEP = True


@dataclass(frozen=True)
class DecisionStepArtifacts:
    envelope: Any
    explanation: Any
    executable_action: executable_action_contract.ExecutableAction
    autonomy_decision: Any


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
        trace.record(
            event_type="decision_issued",
            step_index=step_index,
            payload={
                "decision_id": envelope.decision.decision_id,
                "action": envelope.decision.action,
                "correlation_id": envelope.decision.correlation_id,
                "policy_explanation": {
                    "policy_id": explanation.policy_id,
                    "summary": explanation.summary,
                    "factors": list(explanation.factors),
                },
                "attempt_index": attempt_index,
            },
        )
        executable_action = self._project_executable_action(
            request=request,
            state=state,
            envelope=envelope,
        )
        autonomy_decision = evaluate_autonomy_tier(
            action_type=str(envelope.decision.action),
            autonomy_tier=request.autonomy_tier,
            approval_policy=dict(request.approval_policy or {}),
        )
        return DecisionStepArtifacts(
            envelope=envelope,
            explanation=explanation,
            executable_action=executable_action,
            autonomy_decision=autonomy_decision,
        )
    decide = evaluate

    def _project_executable_action(self, *, request: Any, state: Any, envelope: Any) -> executable_action_contract.ExecutableAction:
        decision_id = str(envelope.decision.decision_id)
        payload = dict(envelope.decision.payload or {})
        payload.setdefault("tenant_id", str(getattr(request, "tenant_id", "") or ""))
        payload.setdefault("business_id", str(getattr(request, "business_id", "") or ""))
        payload.setdefault("user_id", str(getattr(request, "user_id", "") or ""))
        payload.setdefault("autonomy_tier", str(getattr(request, "autonomy_tier", "supervised") or "supervised"))
        payload.setdefault("approval_policy", dict(getattr(request, "approval_policy", {}) or {}))
        payload.setdefault("constraints", dict(getattr(request, "constraints", {}) or {}))
        payload.setdefault("economy", dict(getattr(request, "economy", {}) or {}))
        payload.setdefault("goal_plan", dict(getattr(request, "meta", {}).get("goal_plan") or {}))
        payload.setdefault("previous_feedback", dict(getattr(request, "meta", {}).get("previous_feedback") or {}))
        action_type = str(envelope.decision.action)
        capability_plan = self._contract._capability_aware_planner.plan_action(
            request=request,
            state=state,
            action_type=action_type,
            payload=payload,
        )
        payload["capability_planning"] = capability_plan.to_dict()
        enforce_capability_plan = self._should_enforce_capability_plan()
        payload_patch = dict(capability_plan.payload_patch)
        if enforce_capability_plan or not capability_plan.allowed:
            payload.update(payload_patch)
            if capability_plan.allowed:
                action_type = str(capability_plan.action_type)
            else:
                payload.setdefault('operator_required', True)
                payload.setdefault('status', 'capability_preflight_blocked')
                payload.setdefault('capability_blocked', True)
                if action_type != 'notify_owner':
                    action_type = 'notify_owner'
        else:
            payload.update(self._non_effectful_capability_patch(payload_patch))
            if capability_plan.fallback_used and str(capability_plan.action_type or action_type) != action_type:
                action_type = str(capability_plan.action_type)
        action_payload = {
            "action_id": f"action:{decision_id}",
            "action_type": action_type,
            "channel": str(request.channel),
            "payload": payload,
            "decision_id": decision_id,
            "correlation_id": str(envelope.decision.correlation_id or ""),
            "objective_name": "profit_adjusted_growth",
        }
        return getattr(executable_action_contract, "ExecutableAction")(**action_payload)

    def _should_enforce_capability_plan(self) -> bool:
        executor = getattr(self._contract, '_executor', None)
        if executor is None:
            return False
        module_name = str(getattr(type(executor), '__module__', '') or '')
        if module_name.startswith('runtime.'):
            return True
        return bool(getattr(executor, 'enforce_capability_planning', False))

    @staticmethod
    def _non_effectful_capability_patch(payload_patch: dict[str, Any]) -> dict[str, Any]:
        preserved_keys = {
            'capability_diagnostics',
            'execution_verdict',
            'policy_verdict',
            'routing_explanation',
            'capability_fallback_kind',
            'capability_fallback_reason',
            'capability_fallback_from',
        }
        return {
            key: value
            for key, value in payload_patch.items()
            if key in preserved_keys
        }


__all__ = ["CANON_AUTONOMY_DECISION_STEP", "AutonomyDecisionStep", "DecisionStepArtifacts"]
