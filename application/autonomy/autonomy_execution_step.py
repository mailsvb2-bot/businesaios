from __future__ import annotations

from execution.runtime_keys import ACTION_BUDGET_KEY
from dataclasses import replace
from typing import Any

from kernel.decision_crypto import envelope_has_required_signature_fields, signed_envelope_from_decision
from application.headless.execution_gateway import execute_headless_envelope
from runtime.execution.executor_result import ExecutionResult


CANON_AUTONOMY_EXECUTION_STEP = True
CANON_AUTONOMY_EXECUTION_STEP_GATEWAY_EXECUTION_OWNER = True


class AutonomyExecutionStep:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract

    def execute(
        self,
        *,
        request: Any,
        executable_action: Any,
        envelope: Any,
        autonomy_decision: Any,
    ) -> ExecutionResult:
        capability_plan_payload = executable_action.payload.get("capability_planning") if isinstance(executable_action.payload, dict) else None
        capability_plan = dict(capability_plan_payload or {})

        if autonomy_decision.blocked_by_policy or autonomy_decision.approval_required:
            error_code = "policy_blocked" if autonomy_decision.blocked_by_policy else "approval_required"
            return ExecutionResult(
                ok=False,
                output={
                    "autonomy_tier": autonomy_decision.tier,
                    "approval_required": bool(autonomy_decision.approval_required),
                    "blocked_by_policy": bool(autonomy_decision.blocked_by_policy),
                    "action_class": autonomy_decision.action_class,
                    "capability_planning": capability_plan,
                },
                error=error_code,
                decision_id=envelope.decision.decision_id,
                correlation_id=envelope.decision.correlation_id,
            )

        if capability_plan and not bool(capability_plan.get("allowed", False)):
            execution_verdict = dict(capability_plan.get("execution_verdict") or {})
            policy_verdict = dict(capability_plan.get("policy_verdict") or {})
            denial_reason = str(capability_plan.get("reason") or execution_verdict.get("reason") or "runtime_capability_disabled")
            return ExecutionResult(
                ok=False,
                output={
                    "blocked_by_policy": True,
                    "operator_required": True,
                    "autonomy_safety": {
                        "allowed": False,
                        "operator_required": True,
                        "reason": denial_reason,
                        "details": {
                            "capability_execution_verdict": execution_verdict,
                            "policy_verdict": policy_verdict,
                        },
                        "next_tier": getattr(request, "autonomy_tier", "supervised"),
                    },
                    "capability_planning": capability_plan,
                    ACTION_BUDGET_KEY: dict(execution_verdict.get("budget") or {}),
                    "bounded_autonomy": dict(execution_verdict.get("budget") or {}),
                    "blast_radius_guard": dict(execution_verdict.get("blast_radius") or {}),
                },
                error=denial_reason,
                decision_id=envelope.decision.decision_id,
                correlation_id=envelope.decision.correlation_id,
            )

        previous_feedback = dict((request.meta or {}).get("previous_feedback") or {})
        safety_verdict = self._contract._autonomy_safety_bundle.evaluate_pre_execution(
            request=request,
            action_type=executable_action.action_type,
            payload=dict(executable_action.payload or {}),
            previous_feedback=previous_feedback,
            event_log=getattr(self._contract, "_event_log", None),
            recent_actions=list(previous_feedback.get("recent_actions") or []),
        )
        executable_action.payload["autonomy_safety"] = safety_verdict.to_dict()
        executable_action.payload["autonomy_policy_snapshot"] = self._contract._autonomy_safety_bundle.build_policy_snapshot(
            request=request,
            safety_verdict=safety_verdict.to_dict(),
        )
        audit_record = self._contract._autonomy_safety_bundle.build_audit_record(
            request=request,
            verdict=safety_verdict.to_dict(),
            runtime_verdict_matched=None,
        )
        executable_action.payload["autonomy_audit"] = audit_record.to_dict()
        if not safety_verdict.allowed:
            details = dict(safety_verdict.details or {})
            return ExecutionResult(
                ok=False,
                output={
                    "blocked_by_policy": not bool(safety_verdict.operator_required),
                    "operator_required": bool(safety_verdict.operator_required),
                    "autonomy_safety": safety_verdict.to_dict(),
                    "autonomy_audit": audit_record.to_dict(),
                    ACTION_BUDGET_KEY: dict(details.get(ACTION_BUDGET_KEY) or {}),
                    "bounded_autonomy": dict(details.get("bounded_autonomy") or {}),
                    "blast_radius_guard": dict(details.get("blast_radius_guard") or {}),
                    "capability_planning": capability_plan,
                },
                error=str(safety_verdict.reason),
                decision_id=envelope.decision.decision_id,
                correlation_id=envelope.decision.correlation_id,
            )

        envelope = self._finalize_execution_envelope(
            request=request,
            original_envelope=envelope,
            executable_action=executable_action,
        )
        result = execute_headless_envelope(executor=self._contract._executor, envelope=envelope)
        if isinstance(result.output, dict):
            details = dict(safety_verdict.details or {})
            result.output.setdefault("autonomy_safety", safety_verdict.to_dict())
            result.output.setdefault("autonomy_audit", audit_record.to_dict())
            result.output.setdefault("capability_planning", capability_plan)
            result.output.setdefault(ACTION_BUDGET_KEY, dict(details.get(ACTION_BUDGET_KEY) or {}))
            result.output.setdefault("bounded_autonomy", dict(details.get("bounded_autonomy") or {}))
            result.output.setdefault("blast_radius_guard", dict(details.get("blast_radius_guard") or {}))
        return result

    def _finalize_execution_envelope(self, *, request: Any, original_envelope: Any, executable_action: Any) -> Any:
        final_payload = dict(getattr(original_envelope.decision, "payload", {}) or {})
        final_payload.update(dict(executable_action.payload or {}))
        final_payload["autonomy_tier"] = str(getattr(request, "autonomy_tier", "supervised") or "supervised")
        final_payload.setdefault("approval_policy", dict(getattr(request, "approval_policy", {}) or {}))
        final_payload.setdefault("constraints", dict(getattr(request, "constraints", {}) or {}))
        final_payload.setdefault("economy", dict(getattr(request, "economy", {}) or {}))
        final_payload.setdefault("autonomy_policy_snapshot", self._contract._autonomy_safety_bundle.build_policy_snapshot(request=request, safety_verdict=final_payload.get("autonomy_safety") or {}))

        final_decision = replace(
            original_envelope.decision,
            action=str(executable_action.action_type),
            payload=final_payload,
        )
        if envelope_has_required_signature_fields(original_envelope):
            keyring = getattr(self._contract, "_decision_keyring", None)
            if keyring is not None:
                return signed_envelope_from_decision(decision=final_decision, keyring=keyring)
        return replace(original_envelope, decision=final_decision)


__all__ = [
    "CANON_AUTONOMY_EXECUTION_STEP",
    "CANON_AUTONOMY_EXECUTION_STEP_GATEWAY_EXECUTION_OWNER",
    "AutonomyExecutionStep",
]
