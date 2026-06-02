from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.canonical_autonomy_safety import canonical_autonomy_safety_decision
from execution.canonical_operator_handoff import canonical_operator_handoff
from execution.headless_trace import HeadlessTrace
from execution.operator_handoff_policy import OperatorHandoffPolicy
from execution.runtime_keys import ACTION_BUDGET_KEY

CANON_AUTONOMY_FEEDBACK_STEP = True


class AutonomyFeedbackStep:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract
        self._handoff_policy = getattr(contract, "_operator_handoff_policy", OperatorHandoffPolicy())

    @staticmethod
    def _safe_dict(value: object) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def build_step(
        self,
        *,
        request: Any,
        state: Any,
        trace: HeadlessTrace,
        step_index: int,
        attempt_index: int,
        envelope: Any,
        explanation: Any,
        executable_action: ExecutableAction,
        autonomy_decision: Any,
        result: Any,
    ) -> tuple[Any, bool]:
        retry_info = self._contract._retry_taxonomy.classify(
            ok=bool(result.ok),
            error=result.error,
        )
        normalized_outcome = self._contract._outcome_normalizer.normalize(
            output=result.output,
            payload=dict(envelope.decision.payload or {}),
        )
        trace.record(
            event_type="action_executed",
            step_index=step_index,
            payload={
                "decision_id": envelope.decision.decision_id,
                "ok": bool(result.ok),
                "error": result.error,
                "correlation_id": result.correlation_id,
                "output": dict(result.output or {}) if isinstance(result.output, dict) else {},
                "normalized_outcome": dict(normalized_outcome),
                "retry_classification": asdict(retry_info),
                "autonomy_decision": {
                    "tier": autonomy_decision.tier,
                    "action_class": autonomy_decision.action_class,
                    "allowed": autonomy_decision.allowed,
                    "approval_required": autonomy_decision.approval_required,
                    "blocked_by_policy": autonomy_decision.blocked_by_policy,
                },
                "attempt_index": attempt_index,
            },
        )
        action_result = self._project_action_result(action=executable_action, result=result)
        feedback = self._read_feedback(
            request=request,
            state=state,
            envelope=envelope,
            executable_action=executable_action,
            action_result=action_result,
            result=result,
            step_index=step_index,
        )
        closed_loop_service = getattr(self._contract, "_closed_loop_service", None)
        if callable(getattr(closed_loop_service, "enrich", None)):
            closed_loop_artifacts = closed_loop_service.enrich(
                request=request,
                state=state,
                executable_action=executable_action,
                action_result=action_result,
                execution_result=result,
                autonomy_decision=autonomy_decision,
                feedback=feedback,
            )
            action_result = closed_loop_artifacts.action_result
            feedback = dict(closed_loop_artifacts.feedback)
        feedback.setdefault("retry_classification", asdict(retry_info))
        if getattr(self._contract, "_revenue_outcome_projector", None) is not None:
            feedback["revenue_outcome"] = dict(
                self._contract._revenue_outcome_projector.project(
                    feedback=feedback,
                    action_result=action_result,
                )
            )
        feedback.setdefault("policy_explanation", asdict(explanation))
        feedback.setdefault("action_type", str(executable_action.action_type or ""))
        feedback.setdefault("decision_id", str(getattr(envelope.decision, "decision_id", "") or ""))
        feedback.setdefault("correlation_id", str(getattr(envelope.decision, "correlation_id", "") or getattr(result, "correlation_id", "") or ""))
        feedback.setdefault("normalized_outcome", dict(normalized_outcome))
        feedback.setdefault("autonomy_tier", request.autonomy_tier)
        feedback.setdefault("approval_required", bool(autonomy_decision.approval_required))
        feedback.setdefault("blocked_by_policy", bool(autonomy_decision.blocked_by_policy))
        feedback.setdefault(
            "verification_failed",
            bool(feedback.get("executed", False)) and not bool(feedback.get("verified", False)),
        )
        feedback.setdefault("handoff_reason", autonomy_decision.handoff_reason)
        goal_score = self._contract._scenario_goal_score_engine.score(
            scenario=(request.meta or {}).get("scenario"),
            goal=request.goal,
            feedback=feedback,
            step_ok=bool(action_result.executed),
        )
        feedback["goal_score"] = float(goal_score.value)
        feedback["goal_score_reasons"] = list(goal_score.reasons)
        goal_evaluation = self._contract._goal_evaluator.evaluate(
            request=request,
            step_feedback=feedback,
            step_verified=bool(action_result.verified),
            operator_required=bool(action_result.operator_required),
            consecutive_failures=int((request.meta or {}).get("previous_feedback", {}).get("consecutive_failures") or 0),
            step_index=step_index,
        )
        feedback["goal_evaluation"] = goal_evaluation.to_dict()
        if isinstance(result.output, dict) and "autonomy_safety" in result.output:
            feedback["autonomy_safety"] = dict(result.output.get("autonomy_safety") or {})
        if isinstance(result.output, dict) and "autonomy_audit" in result.output:
            feedback["autonomy_audit"] = dict(result.output.get("autonomy_audit") or {})
        if isinstance(result.output, dict) and ACTION_BUDGET_KEY in result.output:
            feedback[ACTION_BUDGET_KEY] = dict(result.output.get(ACTION_BUDGET_KEY) or {})
            feedback["action_budget_state"] = dict(
                dict(result.output.get(ACTION_BUDGET_KEY) or {}).get("snapshot_after") or {}
            )
        if isinstance(result.output, dict) and "capability_planning" in result.output:
            feedback["capability_planning"] = dict(result.output.get("capability_planning") or {})
        if isinstance(result.output, dict) and "bounded_autonomy" in result.output:
            feedback["bounded_autonomy"] = dict(result.output.get("bounded_autonomy") or {})
        if isinstance(result.output, dict) and "blast_radius_guard" in result.output:
            feedback["blast_radius_guard"] = dict(result.output.get("blast_radius_guard") or {})

        feedback["autonomy_safety_decision"] = canonical_autonomy_safety_decision(
            request=request,
            safety_verdict=dict(feedback.get("autonomy_safety") or {}),
            bounded_autonomy=dict(feedback.get("bounded_autonomy") or {}),
            blast_radius_guard=dict(feedback.get("blast_radius_guard") or {}),
            safe_self_driving=dict(feedback.get("safe_self_driving") or {}),
            next_tier_context=dict(feedback.get("next_tier_context") or {}),
        )
        if bool(feedback["autonomy_safety_decision"].get("handoff_triggered", False)) or bool(feedback.get("operator_required", False)):
            feedback["operator_handoff"] = canonical_operator_handoff(
                {
                    "run_id": trace.run_id,
                    "step_index": int(step_index),
                    "decision_id": envelope.decision.decision_id,
                    "action": envelope.decision.action,
                    "autonomy_tier": request.autonomy_tier,
                    "approval_required": bool(autonomy_decision.approval_required),
                    "blocked_by_policy": bool(autonomy_decision.blocked_by_policy),
                    "verification_failed": bool(feedback.get("verification_failed", False)),
                    "handoff_reason": feedback.get("handoff_reason"),
                    "reason": retry_info.reason,
                    "bounded_autonomy_reason": dict(feedback.get("bounded_autonomy") or {}).get("reason"),
                    "blast_radius_reason": dict(feedback.get("blast_radius_guard") or {}).get("reason"),
                    "safe_self_driving_reason": dict(feedback.get("safe_self_driving") or {}).get("reason"),
                    "next_tier": dict(feedback.get("next_tier_context") or {}).get("suggested_tier") or request.autonomy_tier,
                    "handoff_state": "awaiting_operator",
                },
                next_tier_context=dict(feedback.get("next_tier_context") or {}),
                opportunity_signals=list(feedback.get("opportunity_signals") or []),
            )

        if self._contract._effect_journal is not None:
            self._contract._effect_journal.append(
                run_id=trace.run_id,
                step_index=step_index,
                decision_id=str(envelope.decision.decision_id),
                action=str(envelope.decision.action),
                effect=dict(normalized_outcome),
            )

        self._record_handoff_if_needed(
            trace=trace,
            step_index=step_index,
            envelope=envelope,
            request=request,
            retry_info=retry_info,
            autonomy_decision=autonomy_decision,
            feedback=feedback,
        )

        self_healing = self._contract._self_healing_retry_engine.evaluate(
            action_type=executable_action.action_type,
            retry_kind=retry_info.kind,
            result_error=result.error,
            feedback=feedback,
            attempt_index=attempt_index,
        )
        feedback["self_healing_retry"] = self_healing.to_dict()
        plan = self._contract._retry_executor_policy.evaluate(
            attempt_index=attempt_index,
            retry_kind=self_healing.retry_kind,
            step_ok=bool(action_result.executed),
        )
        should_retry = bool(plan.should_retry and self_healing.should_retry)
        if should_retry:
            trace.record(
                event_type="retry_scheduled",
                step_index=step_index,
                payload={
                    "attempt_index": attempt_index,
                    "next_attempt_index": plan.next_attempt_index,
                    "reason": plan.reason,
                    "self_healing": self_healing.to_dict(),
                },
            )
            return None, True

        step = self._contract._step_builder.build(
            step_index=step_index,
            action=executable_action,
            action_result=action_result,
            feedback=feedback,
        )
        return step, False

    def _record_handoff_if_needed(
        self,
        *,
        trace: HeadlessTrace,
        step_index: int,
        envelope: Any,
        request: Any,
        retry_info: Any,
        autonomy_decision: Any,
        feedback: dict[str, Any],
    ) -> None:
        if self._contract._operator_handoff_store is None:
            return
        bounded = dict(feedback.get("bounded_autonomy") or {})
        blast = dict(feedback.get("blast_radius_guard") or {})
        safe_loop = dict(feedback.get("safe_self_driving") or {})
        if not self._handoff_policy.should_handoff(
            retry_kind=retry_info.kind,
            blocked_by_policy=bool(autonomy_decision.blocked_by_policy),
            approval_required=bool(autonomy_decision.approval_required),
            bounded_operator_required=bool(bounded.get("operator_required", False)),
            blast_radius_denied=str(blast.get("reason") or "") == "blast_radius_exceeded",
            safe_loop_stop=bool(safe_loop.get("should_stop", False)),
        ):
            return
        payload = self._handoff_policy.build_payload(
            trace=trace,
            step_index=step_index,
            envelope=envelope,
            request=request,
            retry_info=retry_info,
            autonomy_decision=autonomy_decision,
            feedback=feedback,
        )
        next_tier_context = dict(feedback.get("next_tier_context") or {})
        opportunity_signals = list(feedback.get("opportunity_signals") or [])
        write_closed_loop = getattr(self._contract._operator_handoff_store, "write_closed_loop_record", None)
        if callable(write_closed_loop):
            write_closed_loop(
                run_id=trace.run_id,
                step_index=step_index,
                payload=payload,
                next_tier_context=next_tier_context,
                opportunity_signals=opportunity_signals,
            )
            return
        self._contract._operator_handoff_store.write_record(
            run_id=trace.run_id,
            step_index=step_index,
            payload=payload,
        )

    def _read_feedback(
        self,
        *,
        request: Any,
        state: Any,
        envelope: Any,
        executable_action: ExecutableAction,
        action_result: ActionResult,
        result: Any,
        step_index: int,
    ) -> dict[str, Any]:
        if self._contract._feedback_reader is None:
            return {
                "goal": request.goal,
                "step_index": int(step_index),
                "decision_id": envelope.decision.decision_id,
                "action_id": executable_action.action_id,
                "action": executable_action.action_type,
                "ok": bool(action_result.executed),
                "attempted": bool(action_result.attempted),
                "executed": bool(action_result.executed),
                "goal_reached": False,
                "error": result.error,
                "verified": bool(action_result.verified),
                "operator_required": bool(action_result.operator_required),
                "verification_status": "unverified",
                "verification_confidence": 0.0,
                "external_refs": [],
                "evidence_status": "unverified",
                "evidence": {},
            }
        payload = self._contract._feedback_reader.read(
            request=request,
            state=state,
            envelope=envelope,
            executable_action=executable_action,
            action_result=action_result,
            result=result,
            step_index=step_index,
        )
        return dict(payload or {})

    @classmethod
    def _project_action_result(cls, *, action: ExecutableAction, result: Any) -> ActionResult:
        output = dict(result.output or {}) if isinstance(result.output, dict) else {"output": result.output}
        action_payload = dict(getattr(action, 'payload', {}) or {})
        for key in (
            'operator_required',
            'status',
            'blocked_by_policy',
            'approval_required',
            'capability_blocked',
            'capability_fallback_kind',
            'capability_fallback_reason',
            'capability_fallback_from',
            'capability_diagnostics',
            'execution_verdict',
            'policy_verdict',
            'routing_explanation',
            'capability_planning',
        ):
            if key not in output and key in action_payload:
                output[key] = action_payload.get(key)
        effector = output.get("effector") if isinstance(output.get("effector"), dict) else {}
        attempted = bool(effector.get("attempted", result.ok or bool(effector) or output.get("attempted", False)))
        executed = bool(effector.get("executed", result.ok and not output.get("approval_required") and not output.get("blocked_by_policy")))
        verified = bool(effector.get("verified", output.get("verified", False)))
        operator_required = bool(
            effector.get(
                "operator_required",
                output.get("operator_required", False) or output.get("approval_required") or output.get("blocked_by_policy"),
            )
        )
        status = "failed"
        if output.get("blocked_by_policy"):
            status = "blocked_by_policy"
        elif output.get("approval_required"):
            status = "approval_required"
        elif operator_required:
            status = "operator_required"
        elif verified:
            status = "verified"
        elif executed:
            status = "executed"
        elif attempted:
            status = "attempted"
        elif not bool(result.ok) and result.error:
            status = "failed"
        payload = {
            **output,
            "attempted": attempted,
            "executed": executed,
            "verified": verified,
            "operator_required": operator_required,
        }
        return ActionResult(
            action_id=action.action_id,
            status=status,
            message=str(result.error or ""),
            payload=payload,
        )


__all__ = ["CANON_AUTONOMY_FEEDBACK_STEP", "AutonomyFeedbackStep"]
