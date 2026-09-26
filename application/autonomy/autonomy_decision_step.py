from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.autonomy.autonomy_tiers import (
    autonomy_tier_rank,
    evaluate_autonomy_transition,
    normalize_autonomy_tier,
)
from application.decision_runtime.emission import project_decision_proposed_event
from application.headless.decision_gateway import issue_headless_decision
from contracts import executable_action as executable_action_contract
from core.ai.decision_core import (
    project_action_intent,
    project_action_intent_v2,
    project_executable_action,
)
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
        registry = getattr(self._contract, "_agent_identity_registry", None)
        if registry is not None:
            registry.assert_execution_authorized(
                tenant_id=action_intent.tenant_id,
                business_id=action_intent.business_id,
                agent_id=action_intent.agent_id,
                capability=action_intent.action_type,
            )
        self._assert_goal_identity(request=request, action_intent=action_intent)
        self._project_decision_event(envelope=envelope, action_intent=action_intent)
        trace.record(
            event_type="decision_issued",
            step_index=step_index,
            payload={
                "decision_id": envelope.decision.decision_id,
                "action": envelope.decision.action,
                "correlation_id": envelope.decision.correlation_id,
                "action_intent_id": action_intent.intent_id,
                "agent_id": action_intent.agent_id,
                "goal_id": action_intent.goal_id,
                "evidence_refs": list(action_intent.evidence_refs),
                "derived_fact_ref": action_intent.derived_fact_ref,
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
        effective_autonomy_tier = self._effective_autonomy_tier(
            requested_tier=str(request.autonomy_tier or "supervised"),
            executable_action=executable_action,
        )
        autonomy_decision = evaluate_autonomy_transition(
            decided_action_type=action_intent.action_type,
            executable_action_type=str(executable_action.action_type),
            autonomy_tier=effective_autonomy_tier,
            approval_policy=dict(request.approval_policy or {}),
        ).bind_intent(action_intent)
        return DecisionStepArtifacts(
            envelope=envelope, explanation=explanation, action_intent=action_intent,
            executable_action=executable_action, autonomy_decision=autonomy_decision,
        )

    decide = evaluate

    @staticmethod
    def _effective_autonomy_tier(*, requested_tier: str, executable_action: Any) -> str:
        requested = normalize_autonomy_tier(requested_tier)
        payload = getattr(executable_action, "payload", {}) or {}
        planning = dict(payload.get("capability_planning") or {}) if isinstance(payload, dict) else {}
        capability = dict(planning.get("capability") or {})
        runtime_payload = dict(capability.get("runtime") or {})
        patch = dict(planning.get("payload_patch") or {})
        budget_exceeded = bool(
            runtime_payload.get("error_budget_exceeded")
            or runtime_payload.get("risk_budget_exceeded")
            or patch.get("error_budget_exceeded")
            or patch.get("risk_budget_exceeded")
        )
        if not budget_exceeded:
            return requested
        recommended = str(
            runtime_payload.get("recommended_autonomy_tier")
            or patch.get("recommended_autonomy_tier")
            or ""
        ).strip()
        recommended = normalize_autonomy_tier(recommended, default=requested)
        return recommended if autonomy_tier_rank(recommended) < autonomy_tier_rank(requested) else requested

    @staticmethod
    def _assert_goal_identity(*, request: Any, action_intent: Any) -> None:
        expected = str(getattr(request, "goal_id", "") or "").strip()
        if not expected:
            return
        actual = str(getattr(action_intent, "goal_id", "") or "").strip()
        if actual != expected:
            raise ValueError("action intent goal identity does not match canonical request")

    def _project_decision_event(self, *, envelope: Any, action_intent: Any) -> str | None:
        event_store = getattr(self._contract, "_event_store", None)
        if event_store is None:
            executor = getattr(self._contract, "_executor", None)
            module_name = str(getattr(type(executor), "__module__", "") or "")
            if module_name.startswith("runtime."):
                raise RuntimeError("DECISION_EVENT_STORE_REQUIRED")
            return None
        return project_decision_proposed_event(
            event_store=event_store,
            envelope=envelope,
            action_intent=action_intent,
        )

    def _project_action_intent(self, *, request: Any, envelope: Any) -> Any:
        payload = self._intent_payload(request=request, envelope=envelope)
        envelope_version = int(
            getattr(envelope, "envelope_version", getattr(envelope.decision, "envelope_version", 1))
            or 1
        )
        if envelope_version >= 2:
            return project_action_intent_v2(
                decision=envelope.decision,
                payload_hash=str(getattr(envelope, "payload_hash", "") or ""),
                channel=str(request.channel),
                tenant_id=str(getattr(request, "tenant_id", "") or ""),
                business_id=str(getattr(request, "business_id", "") or ""),
            )
        return project_action_intent(
            decision_id=str(envelope.decision.decision_id),
            correlation_id=str(envelope.decision.correlation_id or ""),
            decided_action_type=str(envelope.decision.action),
            channel=str(request.channel), tenant_id=str(getattr(request, "tenant_id", "") or ""),
            business_id=str(getattr(request, "business_id", "") or ""), payload=payload,
            requested_by=str(getattr(envelope.decision, "issuer_id", "sovereign_decision") or "sovereign_decision"),
            agent_id=str(getattr(envelope.decision, "issuer_id", "sovereign_decision") or "sovereign_decision"),
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
