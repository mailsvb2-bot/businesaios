from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from contracts.action_result import ActionResult
    from contracts.executable_action import ExecutableAction
    from execution.closed_loop_orchestrator import ClosedLoopCycleResult, ClosedLoopOrchestrator
else:
    ActionResult = Any  # type: ignore[misc,assignment]
    ExecutableAction = Any  # type: ignore[misc,assignment]
    ClosedLoopCycleResult = Any  # type: ignore[misc,assignment]
    ClosedLoopOrchestrator = Any  # type: ignore[misc,assignment]

CANON_HEADLESS_CLOSED_LOOP = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class HeadlessClosedLoopArtifacts:
    action_result: ActionResult
    cycle_result: ClosedLoopCycleResult
    feedback: dict[str, Any]


class HeadlessClosedLoopService:
    def __init__(self, *, orchestrator: ClosedLoopOrchestrator) -> None:
        self._orchestrator = orchestrator

    def enrich(self, *, request: Any, state: Any, executable_action: ExecutableAction, action_result: ActionResult, execution_result: Any, autonomy_decision: Any, feedback: Mapping[str, Any]) -> HeadlessClosedLoopArtifacts:
        from execution.closed_loop_orchestrator import ClosedLoopCycleInput
        from application.effects.effect_verification_bridge import extract_router_result_from_feedback, normalize_feedback_contract

        original = dict(feedback or {})
        normalized = normalize_feedback_contract(feedback)
        cycle = self._orchestrator.run_cycle(
            cycle_input=ClosedLoopCycleInput(
                action=self._build_action_payload(request=request, executable_action=executable_action, autonomy_decision=autonomy_decision),
                world_state=state,
                execution_receipt=self._build_execution_receipt(executable_action=executable_action, execution_result=execution_result, action_result=action_result, autonomy_decision=autonomy_decision),
                feedback=normalized,
                router_evidence=extract_router_result_from_feedback(normalized),
                requested_tier=getattr(request, "autonomy_tier", "supervised"),
                current_tier=getattr(request, "autonomy_tier", "supervised"),
                approval_required=bool(getattr(autonomy_decision, "approval_required", False)),
                budget_allowed=not bool(_safe_dict(getattr(execution_result, "output", {})).get("budget_blocked", False)),
                blast_radius_allowed=not bool(getattr(autonomy_decision, "blocked_by_policy", False)),
            )
        )
        return HeadlessClosedLoopArtifacts(action_result=action_result, cycle_result=cycle, feedback=self._merge_feedback(dict(normalized or {}), cycle, original_feedback=original))

    @staticmethod
    def _build_action_payload(*, request: Any, executable_action: ExecutableAction, autonomy_decision: Any) -> dict[str, Any]:
        from execution.action_verification_policy import determine_external_confirmation_mode
        from execution.action_catalog import get_action_spec

        payload = dict(executable_action.payload or {})
        action_class = str(getattr(autonomy_decision, "action_class", "") or "").strip()
        if not action_class:
            action_class = str(get_action_spec(executable_action.action_type).action_class or "").strip()
        category = str(payload.get("action_category") or payload.get("effect_category") or payload.get("execution_category") or action_class or ("advisory" if action_class == "advisory" else "effectful"))
        verification_seed = {"action_type": executable_action.action_type, "action_category": category, "external_confirmation_mode": payload.get("external_confirmation_mode")}
        external_confirmation_mode = determine_external_confirmation_mode(verification_seed, default_mode="required")
        return {**payload, "action_id": executable_action.action_id, "action_type": executable_action.action_type, "channel": executable_action.channel, "decision_id": executable_action.decision_id, "correlation_id": executable_action.correlation_id, "objective_name": executable_action.objective_name, "tenant_id": getattr(request, "tenant_id", ""), "business_id": getattr(request, "business_id", ""), "action_category": category, "external_confirmation_mode": external_confirmation_mode}

    @staticmethod
    def _build_execution_receipt(*, executable_action: ExecutableAction, execution_result: Any, action_result: ActionResult, autonomy_decision: Any) -> dict[str, Any]:
        output = _safe_dict(getattr(execution_result, "output", None))
        return {"action_id": executable_action.action_id, "action_type": executable_action.action_type, "decision_id": executable_action.decision_id, "correlation_id": executable_action.correlation_id, "status": action_result.status, "summary": str(getattr(execution_result, "error", None) or output.get("message") or action_result.message or ""), "ok": bool(getattr(execution_result, "ok", False)), "error": getattr(execution_result, "error", None), "output": output, "attempted": action_result.attempted, "executed": action_result.executed, "verified": action_result.verified, "operator_required": action_result.operator_required, "autonomy_tier": str(getattr(autonomy_decision, "tier", "") or ""), "approval_required": bool(getattr(autonomy_decision, "approval_required", False)), "blocked_by_policy": bool(getattr(autonomy_decision, "blocked_by_policy", False))}

    @staticmethod
    def _merge_feedback(feedback: dict[str, Any], cycle_result: ClosedLoopCycleResult, *, original_feedback: Mapping[str, Any] | None = None) -> dict[str, Any]:
        from application.effects.canonical_execution_feedback import canonical_execution_feedback, canonical_headless_step_artifact, canonical_persisted_outcome, canonical_world_state_row

        verification = dict(cycle_result.verification_result.get("verification") or {})
        feedback["verified"] = bool(cycle_result.verification_result.get("verified", feedback.get("verified", False)))
        original_status = str((original_feedback or {}).get("verification_status") or feedback.get("verification_status") or "").strip()
        computed = str(verification.get("status") or original_status or "unknown")
        feedback["verification_status"] = original_status if str(verification.get("source_of_truth") or "") == "router" and original_status and original_status not in {"unknown", "unverified", "missing_external_confirmation"} and computed == "verified" else computed
        feedback["verification_confidence"] = verification.get("confidence", feedback.get("verification_confidence"))
        feedback["external_refs"] = list(verification.get("external_refs") or feedback.get("external_refs") or [])
        feedback["evidence_status"] = feedback["verification_status"]
        feedback["evidence"] = {"router_result": dict(verification), "world_state_update": dict(cycle_result.world_state_update or {}), "persisted_memory_evidence": dict(cycle_result.persisted_memory_evidence or {})}
        feedback["next_tier_context"] = dict(cycle_result.next_tier_context or {})
        feedback["opportunity_signals"] = list(cycle_result.opportunity_signals or [])
        feedback["memory_evidence_patch"] = dict(cycle_result.persisted_memory_evidence or {})
        snapshot = canonical_execution_feedback(feedback=feedback)
        feedback["execution_feedback"] = snapshot
        feedback["persisted_outcome"] = canonical_persisted_outcome(snapshot)
        feedback["world_state_row"] = canonical_world_state_row(snapshot)
        feedback["headless_step_artifact"] = canonical_headless_step_artifact(feedback=feedback)
        return feedback


__all__ = ["CANON_HEADLESS_CLOSED_LOOP", "HeadlessClosedLoopArtifacts", "HeadlessClosedLoopService"]
