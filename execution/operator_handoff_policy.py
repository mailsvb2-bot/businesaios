from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.canonical_operator_handoff import canonical_operator_handoff


CANON_OPERATOR_HANDOFF_POLICY = True


@dataclass(frozen=True)
class OperatorHandoffPolicy:
    def should_handoff(
        self,
        *,
        retry_kind: str,
        blocked_by_policy: bool,
        approval_required: bool,
        bounded_operator_required: bool = False,
        blast_radius_denied: bool = False,
        safe_loop_stop: bool = False,
    ) -> bool:
        return bool(
            retry_kind == "operator_required"
            or blocked_by_policy
            or approval_required
            or bounded_operator_required
            or blast_radius_denied
            or safe_loop_stop
        )

    def build_payload(
        self,
        *,
        trace: Any,
        step_index: int,
        envelope: Any,
        request: Any,
        retry_info: Any,
        autonomy_decision: Any,
        feedback: dict[str, Any],
    ) -> dict[str, Any]:
        safe_feedback = dict(feedback or {})
        bounded = dict(safe_feedback.get("bounded_autonomy") or {})
        blast = dict(safe_feedback.get("blast_radius_guard") or {})
        safe_loop = dict(safe_feedback.get("safe_self_driving") or {})
        return canonical_operator_handoff(
            {
                "run_id": trace.run_id,
                "step_index": int(step_index),
                "decision_id": envelope.decision.decision_id,
                "action": envelope.decision.action,
                "reason": retry_info.reason,
                "handoff_reason": autonomy_decision.handoff_reason or retry_info.reason,
                "autonomy_tier": request.autonomy_tier,
                "approval_required": bool(autonomy_decision.approval_required),
                "blocked_by_policy": bool(autonomy_decision.blocked_by_policy),
                "verification_failed": not bool(safe_feedback.get("verified", False)),
                "bounded_autonomy_reason": bounded.get("reason"),
                "blast_radius_reason": blast.get("reason"),
                "safe_self_driving_reason": safe_loop.get("reason"),
                "next_tier": str(
                    safe_loop.get("next_tier")
                    or dict(safe_feedback.get("next_tier_context") or {}).get("suggested_tier")
                    or request.autonomy_tier
                ),
                "handoff_state": "awaiting_operator",
            },
            next_tier_context=dict(safe_feedback.get("next_tier_context") or {}),
            opportunity_signals=list(safe_feedback.get("opportunity_signals") or []),
        )


__all__ = ["CANON_OPERATOR_HANDOFF_POLICY", "OperatorHandoffPolicy"]
