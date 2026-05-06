from __future__ import annotations

from typing import Any, Mapping

from execution.autonomy_learning_context import AutonomyLearningContext


CANON_AUTONOMY_LEARNING_CONTEXT_POLICY = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


class AutonomyLearningContextPolicy:
    def compose(self, *, tenant_id: str, business_id: str, goal_family: str, performance_context: Mapping[str, Any] | None = None, capability_context: Mapping[str, Any] | None = None, strategy_hints: tuple[dict[str, Any], ...] = (), retry_profile: Mapping[str, Any] | None = None) -> AutonomyLearningContext:
        perf = _safe_dict(performance_context)
        cap = _safe_dict(capability_context)
        retry = _safe_dict(retry_profile)
        return AutonomyLearningContext(
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            goal_family=str(goal_family or 'default'),
            budget_posture=str(perf.get('recommended_budget_posture') or perf.get('budget_posture') or 'neutral'),
            capability_health=cap,
            strategy_hints=tuple(dict(x) for x in strategy_hints),
            retry_profile=retry,
        )


__all__ = ['CANON_AUTONOMY_LEARNING_CONTEXT_POLICY', 'AutonomyLearningContextPolicy']
