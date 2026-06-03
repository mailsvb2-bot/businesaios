from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from execution.autonomy_learning_context_policy import AutonomyLearningContextPolicy
from execution.capability_health_policy import CapabilityHealthPolicy
from execution.performance_feedback_policy import PerformanceFeedbackPolicy
from execution.strategy_support_policy import StrategySupportPolicy


CANON_EXECUTION_ADAPTATION_FACADE = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


class ExecutionAdaptationFacade:
    def __init__(self) -> None:
        self._performance = PerformanceFeedbackPolicy()
        self._health = CapabilityHealthPolicy()
        self._strategy = StrategySupportPolicy()
        self._learning = AutonomyLearningContextPolicy()

    def build_context(self, *, tenant_id: str, business_id: str, goal_family: str, counters: Mapping[str, Any], spent_total: float, capability_counters: Mapping[str, Any], strategy_feedback: Mapping[str, Any] | None = None, strategy_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        perf_view = self._performance.build_view(counters=counters, spent_total=spent_total)
        health_view = self._health.build_view(counters=capability_counters)
        hints = tuple(x.to_dict() for x in self._strategy.build_hints(goal_family=goal_family, feedback=strategy_feedback, metadata=strategy_metadata))
        context = self._learning.compose(
            tenant_id=tenant_id,
            business_id=business_id,
            goal_family=goal_family,
            performance_context={
                'recommended_budget_posture': perf_view.budget_posture.posture,
            },
            capability_context={
                'health_score': health_view.health_score,
                'health_tier': health_view.health_tier,
            },
            strategy_hints=hints,
            retry_profile={},
        )
        payload = context.to_dict()
        payload['budget_posture_detail'] = perf_view.budget_posture.to_dict()
        payload['strategy_hints'] = hints
        return payload


__all__ = ['CANON_EXECUTION_ADAPTATION_FACADE', 'ExecutionAdaptationFacade']
