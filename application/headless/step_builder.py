from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from application.effects.canonical_execution_feedback import canonical_execution_feedback
from execution.canonical_run_artifacts import canonical_goal_execution_step
from application.headless.models import GoalExecutionStep


CANON_HEADLESS_STEP_BUILDER = True


@dataclass(frozen=True)
class HeadlessStepBuilder:
    def build(
        self,
        *,
        step_index: int,
        action: ExecutableAction,
        action_result: ActionResult,
        feedback: dict[str, Any],
    ) -> GoalExecutionStep:
        refs = feedback.get("external_refs") if isinstance(feedback, dict) else []
        if not isinstance(refs, list):
            refs = list(refs) if isinstance(refs, tuple) else []
        external_ref = str(feedback.get("external_ref") or (refs[0] if refs else "") or "") or None
        executed = bool(feedback.get("executed", action_result.executed))
        attempted = bool(feedback.get("attempted", action_result.attempted))
        verified = bool(feedback.get("verified", action_result.verified))
        operator_required = bool(feedback.get("operator_required", action_result.operator_required))
        execution_feedback = canonical_execution_feedback(
            feedback=feedback,
            action={
                "action_type": action.action_type,
                "action_id": action.action_id,
                "decision_id": action.decision_id,
                "correlation_id": action.correlation_id,
            },
        )
        step = GoalExecutionStep(
            step_index=int(step_index),
            decision_id=action.decision_id,
            action_id=action.action_id,
            action=action.action_type,
            status=str(action_result.status),
            attempted=attempted,
            executed=executed,
            verified=verified,
            operator_required=operator_required,
            correlation_id=action.correlation_id,
            reason=None if executed else (action_result.message or None),
            verification_status=feedback.get("verification_status") or feedback.get("evidence_status"),
            external_ref=external_ref,
            evidence=dict(feedback.get("evidence") or {}),
            payload=dict(action.payload or {}),
            feedback=dict(feedback or {}),
            execution_feedback=execution_feedback,
        )
        return GoalExecutionStep(**{**step.__dict__, 'canonical_step_artifact': canonical_goal_execution_step(step)})


__all__ = ["CANON_HEADLESS_STEP_BUILDER", "HeadlessStepBuilder"]
