from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
CANON_PLANNER_STATE_CONTRACT = True
@dataclass(frozen=True)
class StrategicGoalRecord:
    goal_id: str
    goal: str
    priority: int
    urgency: int
    budget_weight: float
    status: str
    blocked: bool
    progress_score: float
    planning_horizon: str = 'week'
    dependencies: tuple[str, ...] = ()
    strategy_tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    planning_memory: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['dependencies'] = list(self.dependencies)
        payload['strategy_tags'] = list(self.strategy_tags)
        payload['planning_memory'] = dict(self.planning_memory)
        return payload
@dataclass(frozen=True)
class StrategicPlanContext:
    selected_goal_id: str | None
    selected_goal: str | None
    ranked_goal_ids: tuple[str, ...]
    planning_horizon: str
    decomposed_focus: tuple[str, ...] = ()
    deferred_goal_ids: tuple[str, ...] = ()
    blocked_goal_ids: tuple[str, ...] = ()
    reason: str = 'no_eligible_goals'
    evidence_only: bool = True
    must_not_issue_decision: bool = True
    diagnostics: dict[str, Any] = field(default_factory=dict)
    planning_memory_summary: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['ranked_goal_ids'] = list(self.ranked_goal_ids)
        payload['decomposed_focus'] = list(self.decomposed_focus)
        payload['deferred_goal_ids'] = list(self.deferred_goal_ids)
        payload['blocked_goal_ids'] = list(self.blocked_goal_ids)
        payload['planning_memory_summary'] = dict(self.planning_memory_summary)
        return payload
