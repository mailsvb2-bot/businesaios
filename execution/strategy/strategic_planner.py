from __future__ import annotations
from dataclasses import replace
from typing import Any, Iterable, Mapping
from execution.strategy.dependency_graph import DependencyGraph
from execution.strategy.goal_conflict_resolver import GoalConflictResolver
from execution.strategy.goal_decomposer import GoalDecomposer
from execution.strategy.horizon_manager import HorizonManager
from execution.strategy.planner_memory import PlannerMemory
from execution.strategy.planner_state_contract import StrategicGoalRecord, StrategicPlanContext
from execution.strategy.portfolio_allocator import PortfolioAllocator
from execution.strategy.replanning_engine import ReplanningEngine
CANON_STRATEGIC_PLANNER = True
class StrategicPlanner:
    def __init__(
        self,
        *,
        horizon_manager: HorizonManager | None = None,
        goal_decomposer: GoalDecomposer | None = None,
        goal_conflict_resolver: GoalConflictResolver | None = None,
        replanning_engine: ReplanningEngine | None = None,
        portfolio_allocator: PortfolioAllocator | None = None,
        dependency_graph: DependencyGraph | None = None,
        planner_memory: PlannerMemory | None = None,
    ) -> None:
        self._horizon_manager = horizon_manager or HorizonManager()
        self._goal_decomposer = goal_decomposer or GoalDecomposer()
        self._goal_conflict_resolver = goal_conflict_resolver or GoalConflictResolver()
        self._replanning_engine = replanning_engine or ReplanningEngine()
        self._portfolio_allocator = portfolio_allocator or PortfolioAllocator()
        self._dependency_graph = dependency_graph or DependencyGraph()
        self._planner_memory = planner_memory or PlannerMemory()
    def enrich_metadata(self, *, goal: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(metadata or {})
        planning_horizon = self._horizon_manager.resolve(goal=goal, metadata=payload)
        decomposed_focus = self._goal_decomposer.decompose(goal=goal, metadata=payload)
        payload.setdefault('planning_horizon', planning_horizon)
        payload.setdefault('decomposed_focus', list(decomposed_focus))
        tags = payload.get('strategy_tags')
        if not isinstance(tags, list):
            tags = [] if tags is None else [str(tags)]
        if planning_horizon not in tags:
            tags.append(planning_horizon)
        payload['strategy_tags'] = [str(item) for item in tags if str(item).strip()]
        return payload
    def build_record(self, *, item: Any) -> StrategicGoalRecord:
        metadata = self.enrich_metadata(goal=str(getattr(item, 'goal', '')), metadata=getattr(item, 'metadata', {}) or {})
        dependencies = tuple(str(x) for x in (metadata.get('depends_on') or metadata.get('dependencies') or ()) if str(x).strip())
        tags = tuple(str(x) for x in (metadata.get('strategy_tags') or ()) if str(x).strip())
        planning_memory = self._planner_memory.summarize_metadata(metadata=metadata)
        return StrategicGoalRecord(
            goal_id=str(getattr(item, 'goal_id', '')),
            goal=str(getattr(item, 'goal', '')),
            priority=int(getattr(item, 'priority', 50)),
            urgency=int(getattr(item, 'urgency', 50)),
            budget_weight=float(getattr(item, 'budget_weight', 1.0)),
            status=str(getattr(item, 'status', 'queued')),
            blocked=bool(getattr(item, 'blocked', False)),
            progress_score=float(getattr(item, 'progress_score', 0.0)),
            planning_horizon=str(metadata.get('planning_horizon') or 'week'),
            dependencies=dependencies,
            strategy_tags=tags,
            metadata=metadata,
            planning_memory=planning_memory.to_dict(),
        )
    def _annotate_dependency_state(self, *, records: Iterable[StrategicGoalRecord]) -> tuple[list[StrategicGoalRecord], dict[str, Any]]:
        dependency_analysis = self._dependency_graph.analyze(records=records)
        dependency_missing = dict(dependency_analysis.missing_dependencies)
        annotated_records = [
            replace(
                record,
                metadata={
                    **dict(record.metadata),
                    'dependency_analysis': {
                        'dependency_ready': record.goal_id in dependency_analysis.ready_goal_ids,
                        'missing_dependencies': list(dependency_missing.get(record.goal_id, ())),
                        'downstream_goal_ids': list(dependency_analysis.reverse_edges.get(record.goal_id, ())),
                    },
                },
            )
            for record in records
        ]
        return annotated_records, dependency_analysis.to_dict()
    def rank_items(self, *, items: Iterable[Any], base_scores: Mapping[str, float] | None = None) -> tuple[list[Any], dict[str, Any]]:
        score_map = {str(key): float(value) for key, value in dict(base_scores or {}).items()}
        raw_items = tuple(items)
        records = [self.build_record(item=item) for item in raw_items]
        records, dependency_diagnostics = self._annotate_dependency_state(records=records)
        item_by_id = {record.goal_id: item for record, item in zip(records, raw_items)}
        ranked_records = sorted(
            records,
            key=lambda record: (
                bool(dict(record.metadata.get('dependency_analysis') or {}).get('dependency_ready', not record.dependencies)),
                self._portfolio_allocator.advisory_score(record=record, base_score=score_map.get(record.goal_id, 0.0)),
            ),
            reverse=True,
        )
        diagnostics = self._portfolio_allocator.build_diagnostics(ranked_records=ranked_records, base_scores=score_map)
        diagnostics['dependency_graph'] = dependency_diagnostics
        ranked_items = [item_by_id[record.goal_id] for record in ranked_records if record.goal_id in item_by_id]
        return ranked_items, diagnostics
    def explain_selection(self, *, selected_item: Any | None, ranked_items: Iterable[Any], ranking_diagnostics: Mapping[str, Any] | None = None) -> StrategicPlanContext:
        records = [self.build_record(item=item) for item in ranked_items]
        records, dependency_diagnostics = self._annotate_dependency_state(records=records)
        selected_goal_id = None if selected_item is None else str(getattr(selected_item, 'goal_id', '')) or None
        selected_goal = None if selected_item is None else str(getattr(selected_item, 'goal', '')) or None
        selected_record = next((record for record in records if record.goal_id == selected_goal_id), None)
        conflicts = self._goal_conflict_resolver.resolve(selected_goal_id=selected_goal_id, records=records)
        decomposed_focus = tuple(selected_record.metadata.get('decomposed_focus') or ()) if selected_record is not None else ()
        planning_memory_summary = {} if selected_record is None else dict(selected_record.planning_memory)
        return StrategicPlanContext(
            selected_goal_id=selected_goal_id,
            selected_goal=selected_goal,
            ranked_goal_ids=tuple(record.goal_id for record in records),
            planning_horizon='week' if selected_record is None else selected_record.planning_horizon,
            decomposed_focus=tuple(str(x) for x in decomposed_focus if str(x).strip()),
            deferred_goal_ids=tuple(conflicts.get('deferred_goal_ids') or ()),
            blocked_goal_ids=tuple(conflicts.get('blocked_goal_ids') or ()),
            reason='no_eligible_goals' if selected_record is None else 'dependency_aware_highest_ranked_goal',
            diagnostics={
                'dependency_blocked_goal_ids': list(conflicts.get('dependency_blocked_goal_ids') or ()),
                'record_count': len(records),
                'portfolio_allocator': dict(ranking_diagnostics or {}),
                'dependency_graph': dependency_diagnostics,
                'planning_memory_summary': planning_memory_summary,
            },
            planning_memory_summary=planning_memory_summary,
        )
    def classify_feedback(self, *, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        return self._replanning_engine.classify_feedback(feedback=feedback)

    def apply_feedback(self, *, metadata: Mapping[str, Any] | None, feedback_view: Mapping[str, Any] | None, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        return self._planner_memory.apply_feedback(metadata=dict(metadata or {}), feedback_view=dict(feedback_view or {}), feedback=dict(feedback or {}))
