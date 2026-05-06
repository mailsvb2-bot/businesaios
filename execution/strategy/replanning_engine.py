from __future__ import annotations
from typing import Any, Mapping
CANON_REPLANNING_ENGINE = True
class ReplanningEngine:
    def classify_feedback(self, *, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = dict(feedback or {})
        goal_eval = dict(payload.get('goal_evaluation') or {})
        achieved = bool(goal_eval.get('achieved'))
        blocked = bool(payload.get('blocked_by_policy') or payload.get('approval_required'))
        ratio = goal_eval.get('completion_ratio', payload.get('goal_score', 0.0))
        try:
            completion_ratio = max(0.0, min(1.0, float(ratio)))
        except (TypeError, ValueError):
            completion_ratio = 0.0
        if achieved:
            next_mode = 'complete'
        elif blocked:
            next_mode = 'operator_handoff'
        elif completion_ratio >= 0.75:
            next_mode = 'verify_and_close'
        elif completion_ratio > 0.0:
            next_mode = 'continue'
        else:
            next_mode = 'replan'
        return {
            'achieved': achieved,
            'blocked': blocked,
            'completion_ratio': completion_ratio,
            'next_mode': next_mode,
            'reason': str(goal_eval.get('reason') or payload.get('verification_status') or ''),
        }
