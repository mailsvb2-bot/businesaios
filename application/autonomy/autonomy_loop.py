from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, replace
from typing import Any

from application.autonomy.autonomy_decision_step import AutonomyDecisionStep
from application.autonomy.autonomy_execution_step import AutonomyExecutionStep
from application.autonomy.autonomy_feedback_step import AutonomyFeedbackStep
from application.autonomy.autonomy_memory_step import AutonomyMemoryStep
from application.autonomy.autonomy_recovery_semantics import classify_recovery_semantics
from application.autonomy.autonomy_state_assembly import AutonomyStateAssembly
from application.autonomy.autonomy_stop_policy import AutonomyStopPolicy
from execution.business_operating_memory import project_business_memory_contract_bundle
from execution.headless_request_fingerprint import build_headless_request_fingerprint
from execution.headless_trace import HeadlessTrace
from execution.safe_self_driving import SafeSelfDrivingPolicy

CANON_HEADLESS_AUTONOMY_LOOP = True
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutonomyLoopResult:
    completed: bool
    stop_reason: str
    steps: tuple[Any, ...]
    final_feedback: dict[str, Any]
    trace: HeadlessTrace


class AutonomyLoop:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract
        self._state_assembly = AutonomyStateAssembly(contract=contract)
        self._decision_step = AutonomyDecisionStep(contract=contract)
        self._execution_step = AutonomyExecutionStep(contract=contract)
        self._feedback_step = AutonomyFeedbackStep(contract=contract)
        self._memory_step = AutonomyMemoryStep(contract=contract)
        self._stop_policy = AutonomyStopPolicy(contract=contract)
        self._safe_self_driving_policy = getattr(contract, "_safe_self_driving_policy", SafeSelfDrivingPolicy())

    def run(self, request: Any) -> AutonomyLoopResult:
        valid, issues = request.validate()
        if not valid:
            raise ValueError(f"invalid GoalExecutionRequest: {', '.join(issues)}")

        if int(request.max_steps) <= 0:
            raise ValueError("GoalExecutionRequest.max_steps must be > 0")

        fingerprint = build_headless_request_fingerprint(payload=asdict(request))
        guard = self._contract._idempotency_guard
        if guard is not None and not guard.claim(key=fingerprint):
            raise RuntimeError("duplicate_headless_request")

        trace = HeadlessTrace.start(
            goal=request.goal,
            business_id=request.business_id,
            tenant_id=request.tenant_id,
        )
        trace.record(
            event_type="request_received",
            step_index=0,
            payload={
                "goal": request.goal,
                "business_id": request.business_id,
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "region": request.region,
                "max_steps": request.max_steps,
                "profile": dict(request.profile),
                "signals": list(request.signals),
                "constraints": dict(request.constraints),
                "economy": dict(request.economy),
                "meta": dict(request.meta),
                "autonomy_tier": request.autonomy_tier,
                "approval_policy": dict(request.approval_policy),
            },
        )

        steps: list[Any] = []
        previous_feedback: dict[str, Any] = {}
        completed = False
        stop_reason = "max_steps_reached"
        consecutive_failures = 0
        business_memory_context = self._state_assembly.load_business_memory_context(request=request, trace=trace)
        goal_plan_context = self._state_assembly.load_goal_plan_context(request=request, trace=trace)
        performance_context = self._state_assembly.load_performance_context(request=request, trace=trace)
        adaptive_optimization_context = self._state_assembly.load_adaptive_optimization_context(request=request, trace=trace)
        multi_goal_context = self._state_assembly.load_multi_goal_context(request=request, trace=trace)
        owner_path_context = self._state_assembly.load_owner_path_context(request=request, trace=trace)

        for step_index in range(int(request.max_steps)):
            runtime_request = self._state_assembly.build_runtime_request(
                request=request,
                previous_feedback=previous_feedback,
                business_memory_context=business_memory_context,
                goal_plan_context=goal_plan_context,
                performance_context=performance_context,
                adaptive_optimization_context=adaptive_optimization_context,
                multi_goal_context=multi_goal_context,
                owner_path_context=owner_path_context,
            )
            trace.record(
                event_type="step_started",
                step_index=step_index,
                payload={
                    "previous_feedback": dict(previous_feedback),
                    "business_memory": dict(business_memory_context),
                    "goal_plan": dict(goal_plan_context),
                    "performance_learning": dict(performance_context),
                    "multi_goal": dict(multi_goal_context),
                },
            )
            state = self._state_assembly.assemble_state(
                request=runtime_request,
                trace=trace,
                step_index=step_index,
                previous_feedback=previous_feedback,
                business_memory_context=business_memory_context,
            )
            step = self._run_single_step(
                request=runtime_request,
                state=state,
                trace=trace,
                step_index=step_index,
            )
            steps.append(step)
            prior_feedback = dict(previous_feedback)
            previous_feedback = dict(step.feedback)
            recent_summary = self._contract._recent_actions_source.summary_from_step(step=step, run_id=trace.run_id)
            previous_feedback["recent_actions"] = self._contract._recent_actions_source.append(history=prior_feedback.get("recent_actions") or [], summary=recent_summary)
            if getattr(self._contract, "_autonomy_counter_store", None) is not None and recent_summary.executed:
                self._contract._autonomy_counter_store.record_step(tenant_id=request.tenant_id, business_id=request.business_id, recent_action=recent_summary.to_dict())
            business_memory_context = self._memory_step.update_business_memory_after_step(
                request=runtime_request,
                step=step,
                fallback_context=business_memory_context,
                trace=trace,
            )
            goal_plan_context = self._memory_step.update_goal_plan_after_step(
                request=runtime_request,
                step=step,
                fallback_context=goal_plan_context,
                trace=trace,
            )
            performance_context = self._memory_step.update_performance_after_step(
                request=runtime_request,
                step=step,
                fallback_context=performance_context,
                trace=trace,
            )
            adaptive_optimization_context = self._memory_step.update_adaptive_optimization_after_step(
                request=runtime_request,
                step=step,
                fallback_context=adaptive_optimization_context,
                trace=trace,
            )
            self._memory_step.update_capability_health_after_step(
                request=runtime_request,
                step=step,
                trace=trace,
            )
            owner_path_context = self._memory_step.update_owner_path_after_step(
                request=runtime_request,
                step=step,
                fallback_context=owner_path_context,
                trace=trace,
            )
            multi_goal_context = self._memory_step.update_multi_goal_after_step(
                request=runtime_request,
                step=step,
                fallback_context=multi_goal_context,
                trace=trace,
            )
            memory_bundle = project_business_memory_contract_bundle(dict(business_memory_context or {}))
            previous_feedback["business_memory_after_step"] = dict(memory_bundle.get("evidence") or {})
            previous_feedback["business_memory_summary"] = dict(memory_bundle.get("governance_summary") or {})
            previous_feedback["goal_plan"] = dict(goal_plan_context)
            previous_feedback["performance_learning"] = dict(performance_context)
            previous_feedback["multi_goal"] = dict(multi_goal_context)
            previous_feedback["owner_path"] = dict(owner_path_context)
            safe_loop_verdict = self._contract._autonomy_safety_bundle.evaluate_post_step(
                request=runtime_request,
                steps=steps,
                previous_feedback=previous_feedback,
                last_step=step,
                consecutive_failures=consecutive_failures,
            )
            safe_loop_decision = dict(safe_loop_verdict.details.get("safe_self_driving") or {})
            previous_feedback["safe_self_driving"] = safe_loop_decision
            previous_feedback["autonomy_audit"] = self._contract._autonomy_safety_bundle.build_audit_record(request=runtime_request, verdict=safe_loop_verdict.to_dict(), runtime_verdict_matched=True).to_dict()
            if bool(safe_loop_decision.get("should_downgrade")) and str(safe_loop_decision.get("next_tier") or runtime_request.autonomy_tier) != runtime_request.autonomy_tier:
                request = replace(
                    request,
                    autonomy_tier=str(safe_loop_decision.get("next_tier") or runtime_request.autonomy_tier),
                    meta={
                        **dict(request.meta or {}),
                        "safe_self_driving": dict(safe_loop_decision),
                        "autonomy_downgraded_from": runtime_request.autonomy_tier,
                    },
                )
                previous_feedback["autonomy_tier"] = str(safe_loop_decision.get("next_tier") or runtime_request.autonomy_tier)
            if bool(safe_loop_decision.get("should_stop")):
                stop_reason = str(safe_loop_decision.get("reason") or "safe_loop_stop")
                completed = bool(step.feedback.get("goal_evaluation", {}).get("achieved")) or bool(step.feedback.get("goal_reached"))
                break
            recovery_semantics = classify_recovery_semantics(step=step, safe_loop_decision=safe_loop_decision)
            previous_feedback["recovery_semantics"] = recovery_semantics.to_dict()
            stop_eval = self._stop_policy.evaluate(
                request=runtime_request,
                step=step,
                step_index=step_index,
                consecutive_failures=consecutive_failures,
            )
            consecutive_failures = int(stop_eval.consecutive_failures if recovery_semantics.counts_toward_consecutive_failures else 0)
            previous_feedback["consecutive_failures"] = consecutive_failures
            trace.record(
                event_type="step_finished",
                step_index=step_index,
                payload={
                    "attempted": step.attempted,
                    "executed": step.executed,
                    "verified": step.verified,
                    "stop_candidate": dict(step.feedback),
                },
            )
            if stop_eval.should_stop:
                stop_reason = str(stop_eval.stop_reason or stop_reason)
                completed = bool(stop_eval.completed)
                break

        final_feedback = self._memory_step.finalize_feedback(
            previous_feedback=previous_feedback,
            business_memory_context=business_memory_context,
            goal_plan_context=goal_plan_context,
            performance_context=performance_context,
            adaptive_optimization_context=adaptive_optimization_context,
            multi_goal_context=multi_goal_context,
            owner_path_context=owner_path_context,
            steps=steps,
        )
        trace.record(
            event_type="run_finished",
            step_index=max(len(steps) - 1, 0),
            payload={
                "completed": completed,
                "stop_reason": stop_reason,
                "steps_count": len(steps),
            },
        )
        if guard is not None and hasattr(guard, "mark_completed"):
            try:
                guard.mark_completed(key=fingerprint, result_ref=trace.run_id, result_digest=trace.trace_id)
            except Exception as mark_exc:
                logger.warning("autonomy_loop_mark_completed_failed", exc_info=mark_exc)
        return AutonomyLoopResult(
            completed=completed,
            stop_reason=stop_reason,
            steps=tuple(steps),
            final_feedback=final_feedback,
            trace=trace,
        )

    def _run_single_step(self, *, request: Any, state: Any, trace: HeadlessTrace, step_index: int) -> Any:
        attempt_index = 0
        while True:
            decision = self._decision_step.evaluate(
                request=request,
                state=state,
                trace=trace,
                step_index=step_index,
                attempt_index=attempt_index,
            )
            result = self._execution_step.execute(
                request=request,
                executable_action=decision.executable_action,
                envelope=decision.envelope,
                autonomy_decision=decision.autonomy_decision,
            )
            step, should_retry = self._feedback_step.build_step(
                request=request,
                state=state,
                trace=trace,
                step_index=step_index,
                attempt_index=attempt_index,
                envelope=decision.envelope,
                explanation=decision.explanation,
                executable_action=decision.executable_action,
                autonomy_decision=decision.autonomy_decision,
                result=result,
            )
            if not should_retry:
                return step
            attempt_index += 1
