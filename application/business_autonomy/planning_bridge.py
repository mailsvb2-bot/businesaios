from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult
from application.planning.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService

_CANON_PLANNING_HORIZON_PRIORITY = {
    'now': 100,
    'today': 90,
    'day': 90,
    'week': 70,
    'month': 50,
    'quarter': 30,
}


def business_autonomy_multi_goal_runtime_dir() -> Path:
    root = Path(os.getenv('DATA_DIR', '.'))
    path = root / 'runtime' / 'planning_memory' / 'multi_goal'
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class BusinessAutonomyPlanningBridge:
    store: FileMultiGoalPlannerStore

    @classmethod
    def default(cls) -> 'BusinessAutonomyPlanningBridge':
        return cls(store=FileMultiGoalPlannerStore(root_dir=business_autonomy_multi_goal_runtime_dir()))

    def publish_execution(self, *, request: BusinessExecutionRequest, result: BusinessExecutionResult) -> None:
        tenant_id = str(request.envelope.metadata.get('tenant_id') or result.metadata.get('tenant_id') or request.envelope.business_id).strip()
        if not tenant_id:
            tenant_id = request.envelope.business_id
        priority = _priority_for_horizon(str(request.envelope.metadata.get('planning_horizon') or 'week'))
        urgency = _urgency_for_result(result=result)
        planner = MultiGoalPlannerService(store=self.store)
        planner.add_goal(
            tenant_id=tenant_id,
            business_id=request.envelope.business_id,
            goal_id=request.envelope.goal_id,
            goal=str(request.envelope.goal_type or request.envelope.goal_id),
            priority=priority,
            urgency=urgency,
        )


def _priority_for_horizon(planning_horizon: str) -> int:
    normalized = str(planning_horizon or '').strip().lower()
    return _CANON_PLANNING_HORIZON_PRIORITY.get(normalized, 60)


def _urgency_for_result(*, result: BusinessExecutionResult) -> int:
    verdict = str(result.verdict.value if hasattr(result.verdict, 'value') else result.verdict).strip().lower()
    if verdict == 'pending':
        return 95
    if verdict == 'accepted':
        return 85
    if verdict == 'completed':
        return 75
    return 50


__all__ = ['BusinessAutonomyPlanningBridge', 'business_autonomy_multi_goal_runtime_dir']
