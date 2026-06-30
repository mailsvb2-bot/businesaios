from __future__ import annotations
from collections.abc import Iterable
from execution.strategy.planner_state_contract import StrategicGoalRecord
CANON_GOAL_CONFLICT_RESOLVER = True
class GoalConflictResolver:
    def resolve(self, *, selected_goal_id: str | None, records: Iterable[StrategicGoalRecord]) -> dict[str, tuple[str, ...] | str | None]:
        selected = str(selected_goal_id or '')
        blocked: list[str] = []
        deferred: list[str] = []
        dependency_blocked: list[str] = []
        record_list = tuple(records)
        metadata_map = {item.goal_id: dict(item.metadata.get('dependency_analysis') or {}) for item in record_list}
        for item in record_list:
            if item.blocked:
                blocked.append(item.goal_id)
                continue
            if item.goal_id == selected:
                continue
            item_dependency_state = metadata_map.get(item.goal_id, {})
            if item_dependency_state.get('missing_dependencies'):
                dependency_blocked.append(item.goal_id)
                deferred.append(item.goal_id)
                continue
            if selected and selected in item.dependencies:
                dependency_blocked.append(item.goal_id)
                deferred.append(item.goal_id)
                continue
            if item.status != 'completed' and item.goal_id:
                deferred.append(item.goal_id)
        return {
            'selected_goal_id': selected or None,
            'blocked_goal_ids': tuple(blocked),
            'deferred_goal_ids': tuple(deferred),
            'dependency_blocked_goal_ids': tuple(dependency_blocked),
        }
