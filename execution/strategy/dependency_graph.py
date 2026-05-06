from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from execution.strategy.planner_state_contract import StrategicGoalRecord
CANON_DEPENDENCY_GRAPH = True
@dataclass(frozen=True)
class DependencyAnalysis:
    ready_goal_ids: tuple[str, ...]
    blocked_goal_ids: tuple[str, ...]
    completed_goal_ids: tuple[str, ...]
    missing_dependencies: dict[str, tuple[str, ...]]
    reverse_edges: dict[str, tuple[str, ...]]
    evidence_only: bool = True
    must_not_issue_decision: bool = True
    def to_dict(self) -> dict[str, object]:
        return {
            "ready_goal_ids": list(self.ready_goal_ids),
            "blocked_goal_ids": list(self.blocked_goal_ids),
            "completed_goal_ids": list(self.completed_goal_ids),
            "missing_dependencies": {str(k): list(v) for k, v in self.missing_dependencies.items()},
            "reverse_edges": {str(k): list(v) for k, v in self.reverse_edges.items()},
            "evidence_only": True,
            "must_not_issue_decision": True,
        }
class DependencyGraph:
    def analyze(self, *, records: Iterable[StrategicGoalRecord]) -> DependencyAnalysis:
        items = tuple(records)
        completed = {item.goal_id for item in items if item.goal_id and item.status == "completed"}
        all_ids = {item.goal_id for item in items if item.goal_id}
        reverse_edges: dict[str, list[str]] = {goal_id: [] for goal_id in all_ids}
        ready: list[str] = []
        blocked: list[str] = []
        missing: dict[str, tuple[str, ...]] = {}
        for item in items:
            if not item.goal_id:
                continue
            unmet: list[str] = []
            for dep in item.dependencies:
                dep_id = str(dep).strip()
                if not dep_id:
                    continue
                if dep_id in reverse_edges:
                    reverse_edges[dep_id].append(item.goal_id)
                if dep_id not in completed:
                    unmet.append(dep_id)
            if item.status == "completed":
                continue
            if item.blocked or unmet:
                blocked.append(item.goal_id)
                if unmet:
                    missing[item.goal_id] = tuple(sorted(set(unmet)))
            else:
                ready.append(item.goal_id)
        normalized_reverse = {goal_id: tuple(sorted(set(children))) for goal_id, children in reverse_edges.items() if children}
        return DependencyAnalysis(
            ready_goal_ids=tuple(sorted(set(ready))),
            blocked_goal_ids=tuple(sorted(set(blocked))),
            completed_goal_ids=tuple(sorted(completed)),
            missing_dependencies=missing,
            reverse_edges=normalized_reverse,
        )
