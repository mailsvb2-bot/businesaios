from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.capability.capability_operator_view import merge_capability_views, normalize_capability_view
from execution.business_operating_memory import (
    project_business_memory_contract_bundle,
    project_business_memory_feedback_snapshot,
)
from execution.evidence.router import EvidenceRouter, build_evidence_router
from execution.outcome_normalizer import OutcomeNormalizer

CANON_HEADLESS_FEEDBACK_READER = True


def _dictish(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bounded_fallback_allows_goal_completion(*, request: Any, action_type: str, step_index: int) -> bool:
    meta = _dictish(getattr(request, "meta", {}))
    policy = _dictish(meta.get("bounded_fallback_policy"))
    if not policy or not bool(policy.get("enabled", False)):
        return False
    allowed = policy.get("allowed_action_types")
    if isinstance(allowed, (list, tuple, set)) and allowed:
        normalized = {str(item) for item in allowed if str(item).strip()}
        if action_type not in normalized:
            return False
    max_step_index = policy.get("max_step_index")
    if max_step_index is not None:
        try:
            if int(step_index) > int(max_step_index):
                return False
        except (TypeError, ValueError):
            return False
    return True


@dataclass(frozen=True)
class SimpleHeadlessFeedbackReader:
    """
    Conservative default feedback reader.

    No second brain:
    - does not invent decisions
    - does not claim goal completion from mere executor success
    - translates execution outcome into normalized feedback + evidence state
    """

    outcome_normalizer: OutcomeNormalizer = field(default_factory=OutcomeNormalizer)
    evidence_router: EvidenceRouter = field(default_factory=build_evidence_router)

    @classmethod
    def default(cls) -> SimpleHeadlessFeedbackReader:
        return cls(outcome_normalizer=OutcomeNormalizer(), evidence_router=build_evidence_router())

    def read(
        self,
        *,
        request: Any,
        state: Any,
        envelope: Any,
        executable_action: Any,
        action_result: Any,
        result: Any,
        step_index: int,
    ) -> dict[str, Any]:
        del state
        normalized = self.outcome_normalizer.normalize(
            output=getattr(result, "output", None),
            payload=dict(getattr(envelope.decision, "payload", {}) or {}),
        )
        action_payload = _dictish(getattr(action_result, "payload", {}))
        connector_result = _dictish(action_payload.get("effector"))
        evidence = self.evidence_router.verify(
            request=request,
            action=executable_action,
            action_result=action_result,
            connector_result=connector_result,
        )
        terminal_flag = bool(normalized.get("terminal", False))
        feedback_goal_reached = bool(normalized.get("goal_reached", False))
        attempted = bool(getattr(action_result, "attempted", False))
        executed = bool(getattr(action_result, "executed", False))
        verified = bool(evidence.verified) or bool(getattr(action_result, "verified", False))
        operator_required = bool(getattr(action_result, "operator_required", False))
        action_type = str(getattr(executable_action, "action_type", "") or "")
        memory_bundle = project_business_memory_contract_bundle(_dictish(_dictish(getattr(request, "meta", {})).get("business_memory")))
        memory_context = dict(memory_bundle.get("evidence") or {})
        fallback_allowed = _bounded_fallback_allows_goal_completion(
            request=request,
            action_type=action_type,
            step_index=int(step_index),
        )
        goal_reached = bool(executed) and (terminal_flag or feedback_goal_reached) and (
            bool(verified) or bool(fallback_allowed)
        )
        external_refs = tuple(str(item) for item in evidence.external_refs if str(item).strip())
        snapshot = {
            "goal": str(request.goal),
            "step_index": int(step_index),
            "decision_id": str(envelope.decision.decision_id),
            "action_id": str(executable_action.action_id),
            "action": str(envelope.decision.action),
            "ok": bool(executed),
            "attempted": bool(attempted),
            "executed": bool(executed),
            "verified": bool(verified),
            "operator_required": bool(operator_required),
            "error": getattr(result, "error", None),
            "ceo_participated": bool(getattr(request, "ceo", None) and request.ceo.enabled),
            "action_status": str(getattr(action_result, "status", "unknown")),
            "verification_status": str(evidence.status),
            "verification_confidence": float(evidence.confidence),
            "external_ref": external_refs[0] if external_refs else None,
            "external_refs": list(external_refs),
            "evidence_status": str(evidence.status),
            "evidence": evidence.as_dict(),
            "bounded_fallback_used": bool(fallback_allowed and not verified and goal_reached),
            "business_memory_before_step": project_business_memory_feedback_snapshot(memory_context),
        }
        snapshot.update(normalized)
        capability_view = merge_capability_views(
            action_payload,
            _dictish(getattr(result, "output", {})),
            normalized,
        )
        if capability_view:
            snapshot['capability_view'] = dict(capability_view)
            if 'diagnostics' in capability_view:
                snapshot['capability_diagnostics'] = dict(capability_view.get('diagnostics') or {})
            if 'execution_verdict' in capability_view:
                snapshot['execution_verdict'] = dict(capability_view.get('execution_verdict') or {})
            if 'policy_verdict' in capability_view:
                snapshot['policy_verdict'] = dict(capability_view.get('policy_verdict') or {})
        if 'capability_planning' in action_payload:
            snapshot['capability_planning'] = _dictish(action_payload.get('capability_planning'))
        snapshot["goal_reached"] = bool(goal_reached)
        return snapshot


__all__ = ["CANON_HEADLESS_FEEDBACK_READER", "SimpleHeadlessFeedbackReader"]
