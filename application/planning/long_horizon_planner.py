from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.goal_decomposition_engine import GoalDecompositionEngine
from execution.goal_family_classifier import GoalFamilyClassifier
from application.planning.strategy_memory import StrategyMemoryService


CANON_LONG_HORIZON_PLANNER = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class LongHorizonPlanView:
    goal: str
    goal_family: str
    planning_horizon: str
    decomposition_reason: str
    decomposition_id: str
    tasks: tuple[dict[str, Any], ...] = ()
    dependency_edges: tuple[dict[str, str], ...] = ()
    checkpoint_task_ids: tuple[str, ...] = ()
    parallelizable_task_ids: tuple[str, ...] = ()
    next_checkpoint_after_steps: int = 1
    strategy_memory_summary: dict[str, Any] = field(default_factory=dict)
    risk_flags: tuple[str, ...] = ()
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "goal_family": self.goal_family,
            "planning_horizon": self.planning_horizon,
            "decomposition_reason": self.decomposition_reason,
            "decomposition_id": self.decomposition_id,
            "tasks": list(self.tasks),
            "dependency_edges": [dict(edge) for edge in self.dependency_edges],
            "checkpoint_task_ids": list(self.checkpoint_task_ids),
            "parallelizable_task_ids": list(self.parallelizable_task_ids),
            "next_checkpoint_after_steps": int(self.next_checkpoint_after_steps),
            "strategy_memory_summary": dict(self.strategy_memory_summary),
            "risk_flags": list(self.risk_flags),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


class LongHorizonPlanner:
    """Canonical long-horizon planning owner.

    It prepares evidence-only planning context and never becomes an execution or
    decision owner. The resulting structure is meant to be consumed as metadata by
    the existing canonical planning path.
    """

    def __init__(self, *, decomposition_engine: GoalDecompositionEngine | None = None, goal_family_classifier: GoalFamilyClassifier | None = None, strategy_memory: StrategyMemoryService | None = None) -> None:
        self._decomposition_engine = decomposition_engine or GoalDecompositionEngine()
        self._goal_family_classifier = goal_family_classifier or GoalFamilyClassifier()
        self._strategy_memory = strategy_memory

    def _goal_family(self, *, goal: str, metadata: Mapping[str, Any] | None) -> str:
        payload = _safe_dict(metadata)
        explicit = _text(payload.get("goal_family"))
        if explicit:
            return explicit
        detected = _text(self._decomposition_engine.detect_goal_family(goal=goal, metadata=payload))
        if detected and detected != "default":
            return detected
        return self._goal_family_classifier.classify(goal)

    def _memory_context(self, *, tenant_id: str, business_id: str, goal_family: str) -> dict[str, Any]:
        if self._strategy_memory is None:
            return {}
        return self._strategy_memory.load_context(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)

    def build_plan(self, *, tenant_id: str, business_id: str, goal: str, metadata: Mapping[str, Any] | None = None, performance_context: Mapping[str, Any] | None = None) -> LongHorizonPlanView:
        payload = dict(_safe_dict(metadata))
        goal_family = self._goal_family(goal=goal, metadata=payload)
        payload.setdefault("goal_family", goal_family)
        memory_context = self._memory_context(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)
        decomposition = self._decomposition_engine.decompose(goal=goal, metadata=payload, performance_context=performance_context, strategy_memory=memory_context)

        dependency_edges: list[dict[str, str]] = []
        checkpoint_task_ids: list[str] = []
        parallelizable_task_ids: list[str] = []
        for task in decomposition.tasks:
            if task.checkpoint_required:
                checkpoint_task_ids.append(task.task_id)
            if task.parallelizable:
                parallelizable_task_ids.append(task.task_id)
            for dep in task.depends_on:
                dependency_edges.append({"from": dep, "to": task.task_id})

        strategy_memory_summary = {
            "observed_runs": int(memory_context.get("observed_runs") or 0),
            "verified_runs": int(memory_context.get("verified_runs") or 0),
            "successful_runs": int(memory_context.get("successful_runs") or 0),
            "preferred_horizon": _text(memory_context.get("preferred_horizon") or ""),
            "risk_flags": list(memory_context.get("risk_flags") or ()),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }

        return LongHorizonPlanView(
            goal=goal,
            goal_family=decomposition.goal_family,
            planning_horizon=decomposition.planning_horizon,
            decomposition_reason=decomposition.decomposition_reason,
            decomposition_id=decomposition.decomposition_id,
            tasks=tuple(task.to_dict() for task in decomposition.tasks),
            dependency_edges=tuple(dependency_edges),
            checkpoint_task_ids=tuple(checkpoint_task_ids),
            parallelizable_task_ids=tuple(parallelizable_task_ids),
            next_checkpoint_after_steps=max(1, decomposition.checkpoint_every_steps),
            strategy_memory_summary=strategy_memory_summary,
            risk_flags=tuple(decomposition.risk_flags),
        )

    def update_memory_after_feedback(self, *, tenant_id: str, business_id: str, plan_context: Mapping[str, Any] | None, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        if self._strategy_memory is None:
            return {}
        plan = _safe_dict(plan_context)
        goal_family = _text(plan.get("goal_family") or "default") or "default"
        return self._strategy_memory.update_after_feedback(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family, plan_context=plan, feedback=feedback)


__all__ = [
    "CANON_LONG_HORIZON_PLANNER",
    "LongHorizonPlanView",
    "LongHorizonPlanner",
]
