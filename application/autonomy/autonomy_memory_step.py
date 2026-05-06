from __future__ import annotations

from typing import Any

from application.headless.models import GoalExecutionStep
from execution.headless_trace import HeadlessTrace
from runtime.platform.business_memory.second_brain_boundary import sanitize_business_memory_payload


CANON_AUTONOMY_MEMORY_STEP = True


class AutonomyMemoryStep:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract

    def update_business_memory_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        fallback_context: dict[str, Any],
        trace: HeadlessTrace | None = None,
    ) -> dict[str, Any]:
        if self._contract._business_memory_service is None:
            return dict(fallback_context or {})
        try:
            return dict(
                self._contract._business_memory_service.update_after_step(
                    business_id=request.business_id,
                    tenant_id=request.tenant_id,
                    feedback=dict(step.feedback or {}),
                    action_type=str(step.action or ""),
                    request_meta={
                        **dict(request.meta or {}),
                        "goal": request.goal,
                        "constraints": dict(request.constraints or {}),
                    },
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="business_memory_update_failed",
                    step_index=int(step.step_index),
                    payload={
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "action": str(step.action or ""),
                    },
                )
            return dict(fallback_context or {})

    def update_performance_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        fallback_context: dict[str, Any],
        trace: HeadlessTrace | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._contract, "_performance_feedback_learning_service", None)
        if service is None:
            return dict(fallback_context or {})
        try:
            return dict(
                service.update_after_step(
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                    goal=request.goal,
                    feedback=dict(step.feedback or {}),
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="performance_learning_update_failed",
                    step_index=int(step.step_index),
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return dict(fallback_context or {})

    def update_capability_health_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        trace: HeadlessTrace | None = None,
    ) -> None:
        registry = getattr(self._contract, "_capability_health_registry", None)
        service = getattr(self._contract, "_capability_health_scoring_service", None)
        action_type = str(step.action or "")
        if not action_type:
            return
        try:
            if registry is not None:
                registry.update_after_feedback(
                    tenant_id=request.tenant_id,
                    action_type=action_type,
                    feedback=dict(step.feedback or {}),
                )
            elif service is not None:
                update_after_action = getattr(service, "update_after_action_step", None)
                if callable(update_after_action):
                    update_after_action(
                        tenant_id=request.tenant_id,
                        action_type=action_type,
                        feedback=dict(step.feedback or {}),
                    )
                else:
                    service.update_after_step(
                        tenant_id=request.tenant_id,
                        capability_key=action_type,
                        feedback=dict(step.feedback or {}),
                    )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="capability_health_update_failed",
                    step_index=int(step.step_index),
                    payload={"error": type(exc).__name__, "message": str(exc), "action_type": action_type},
                )

    def update_adaptive_optimization_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        fallback_context: dict[str, Any],
        trace: HeadlessTrace | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._contract, "_adaptive_optimization_service", None)
        if service is None:
            return dict(fallback_context or {})
        try:
            updated = service.update_after_step(tenant_id=request.tenant_id, business_id=request.business_id, feedback=dict(step.feedback or {}))
            return dict(updated or {})
        except Exception as exc:
            if trace is not None:
                trace.record(event_type="adaptive_optimization_update_failed", step_index=int(step.step_index), payload={"error": type(exc).__name__, "message": str(exc), "action": str(step.action or "")})
            return dict(fallback_context or {})


    def update_owner_path_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        fallback_context: dict[str, Any],
        trace: HeadlessTrace | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._contract, "_owner_path_service", None)
        if service is None:
            return dict(fallback_context or {})
        try:
            return dict(
                service.update_after_step(
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                    goal=request.goal,
                    feedback=dict(step.feedback or {}),
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="owner_path_update_failed",
                    step_index=int(step.step_index),
                    payload={"error": type(exc).__name__, "message": str(exc)},
                )
            return dict(fallback_context or {})

    def update_multi_goal_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        fallback_context: dict[str, Any],
        trace: HeadlessTrace | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._contract, "_multi_goal_planner_service", None)
        if service is None:
            return dict(fallback_context or {})
        goal_id = str((request.meta or {}).get("goal_id") or "")
        if not goal_id:
            return dict(fallback_context or {})
        try:
            service.update_goal_after_run(
                tenant_id=request.tenant_id,
                business_id=request.business_id,
                goal_id=goal_id,
                feedback=dict(step.feedback or {}),
            )
            return dict(service.load_context(tenant_id=request.tenant_id, business_id=request.business_id) or {})
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="multi_goal_update_failed",
                    step_index=int(step.step_index),
                    payload={"error": type(exc).__name__, "message": str(exc), "goal_id": goal_id},
                )
            return dict(fallback_context or {})

    def update_goal_plan_after_step(
        self,
        *,
        request: Any,
        step: GoalExecutionStep,
        fallback_context: dict[str, Any],
        trace: HeadlessTrace | None = None,
    ) -> dict[str, Any]:
        if self._contract._goal_plan_memory_service is None:
            return dict(fallback_context or {})
        try:
            return dict(
                self._contract._goal_plan_memory_service.update_after_step(
                    tenant_id=request.tenant_id,
                    business_id=request.business_id,
                    goal=request.goal,
                    step_index=int(step.step_index),
                    action_type=str(step.action or ""),
                    feedback=dict(step.feedback or {}),
                )
                or {}
            )
        except Exception as exc:
            if trace is not None:
                trace.record(
                    event_type="goal_plan_update_failed",
                    step_index=int(step.step_index),
                    payload={
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "action": str(step.action or ""),
                    },
                )
            return dict(fallback_context or {})

    @staticmethod
    def finalize_feedback(
        *,
        previous_feedback: dict[str, Any],
        business_memory_context: dict[str, Any],
        goal_plan_context: dict[str, Any],
        performance_context: dict[str, Any],
        adaptive_optimization_context: dict[str, Any],
        multi_goal_context: dict[str, Any],
        owner_path_context: dict[str, Any],
        steps: tuple[Any, ...] | list[Any],
    ) -> dict[str, Any]:
        final_feedback = dict(previous_feedback or {})
        sanitized_business_memory = dict(sanitize_business_memory_payload(dict(business_memory_context or {})) or {})
        final_feedback["business_memory_after_step"] = sanitized_business_memory
        final_feedback["business_memory"] = sanitized_business_memory
        final_feedback["goal_plan"] = dict(goal_plan_context)
        final_feedback["performance_learning"] = dict(performance_context)
        final_feedback["adaptive_optimization"] = dict(adaptive_optimization_context)
        final_feedback["multi_goal"] = dict(multi_goal_context)
        final_feedback["owner_path"] = dict(owner_path_context)
        final_feedback.setdefault(
            "evidence_status",
            str(final_feedback.get("verification_status") or final_feedback.get("evidence_status") or "unverified"),
        )
        final_feedback.setdefault(
            "verification_confidence",
            float(final_feedback.get("verification_confidence") or 0.0),
        )
        if steps:
            last_step = steps[-1]
            final_feedback.setdefault("attempted", bool(last_step.attempted))
            final_feedback.setdefault("executed", bool(last_step.executed))
            final_feedback.setdefault("verified", bool(last_step.verified))
            final_feedback.setdefault("operator_required", bool(last_step.operator_required))
        refs = final_feedback.get("external_refs")
        if isinstance(refs, tuple):
            final_feedback["external_refs"] = list(refs)
        elif not isinstance(refs, list):
            final_feedback["external_refs"] = []
        return final_feedback


__all__ = ["CANON_AUTONOMY_MEMORY_STEP", "AutonomyMemoryStep"]
