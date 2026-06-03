from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from application.planning.long_horizon_planner import LongHorizonPlanner
from execution.goal_family_classifier import GoalFamilyClassifier
from execution.multi_goal_policy import MultiGoalPolicy
from execution.strategy import StrategicPlanner
from execution.strategy_support_policy import StrategySupportPolicy

CANON_MULTI_GOAL_PLANNER = True
MULTI_GOAL_SCHEMA_VERSION = 1


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_key(value: object, *, fallback: str) -> str:
    token = _text(value)
    if not token:
        return fallback
    return token.replace("\\", "_").replace("/", "_").replace(":", "_").replace(" ", "_")


@dataclass(frozen=True)
class GoalQueueItem:
    goal_id: str
    goal: str
    priority: int = 50
    urgency: int = 50
    budget_weight: float = 1.0
    status: str = "queued"
    active: bool = True
    blocked: bool = False
    last_outcome: str = ""
    progress_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GoalQueueItem:
        return cls(
            goal_id=_text(payload.get("goal_id")),
            goal=_text(payload.get("goal")),
            priority=max(0, min(100, _safe_int(payload.get("priority"), default=50))),
            urgency=max(0, min(100, _safe_int(payload.get("urgency"), default=50))),
            budget_weight=max(0.0, _safe_float(payload.get("budget_weight"), default=1.0)),
            status=_text(payload.get("status") or "queued") or "queued",
            active=bool(payload.get("active", True)),
            blocked=bool(payload.get("blocked", False)),
            last_outcome=_text(payload.get("last_outcome")),
            progress_score=max(0.0, min(1.0, _safe_float(payload.get("progress_score")))),
            metadata=dict(_safe_dict(payload.get("metadata"))),
        )


@dataclass(frozen=True)
class MultiGoalPlanSnapshot:
    schema_version: int = MULTI_GOAL_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    queue: tuple[GoalQueueItem, ...] = ()
    active_goal_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "queue": [item.to_dict() for item in self.queue],
            "active_goal_id": self.active_goal_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MultiGoalPlanSnapshot:
        return cls(
            schema_version=max(1, _safe_int(payload.get("schema_version"), default=MULTI_GOAL_SCHEMA_VERSION)),
            tenant_id=_text(payload.get("tenant_id")),
            business_id=_text(payload.get("business_id")),
            queue=tuple(GoalQueueItem.from_dict(x) for x in (payload.get("queue") or [])),
            active_goal_id=_text(payload.get("active_goal_id")) or None,
        )


class FileMultiGoalPlannerStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, business_id: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback="default") / f"{_safe_key(business_id, fallback='business')}.json"

    def load(self, *, tenant_id: str, business_id: str) -> MultiGoalPlanSnapshot:
        path = self._path(tenant_id=tenant_id, business_id=business_id)
        if not path.exists():
            return MultiGoalPlanSnapshot(tenant_id=str(tenant_id), business_id=str(business_id))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return MultiGoalPlanSnapshot(tenant_id=str(tenant_id), business_id=str(business_id))
        return MultiGoalPlanSnapshot.from_dict(payload)

    def save(self, snapshot: MultiGoalPlanSnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix=".multi_goal_", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path


@dataclass(frozen=True)
class MultiGoalSelection:
    selected_goal_id: str | None
    selected_goal: str | None
    reason: str
    ranked_goal_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_goal_id": self.selected_goal_id,
            "selected_goal": self.selected_goal,
            "reason": self.reason,
            "ranked_goal_ids": list(self.ranked_goal_ids),
        }


class MultiGoalPlannerService:
    def __init__(self, *, store: FileMultiGoalPlannerStore, strategic_planner: StrategicPlanner | None = None, policy: MultiGoalPolicy | None = None, goal_family_classifier: GoalFamilyClassifier | None = None, strategy_support_policy: StrategySupportPolicy | None = None, long_horizon_planner: LongHorizonPlanner | None = None) -> None:
        self._store = store
        self._strategic_planner = strategic_planner or StrategicPlanner()
        self._policy = policy or MultiGoalPolicy()
        self._goal_family_classifier = goal_family_classifier or GoalFamilyClassifier()
        self._strategy_support_policy = strategy_support_policy or StrategySupportPolicy()
        self._long_horizon_planner = long_horizon_planner

    def _capability_adjustment(self, item: GoalQueueItem) -> float:
        metadata = _safe_dict(item.metadata)
        capability_view = _safe_dict(metadata.get("capability") or metadata.get("capability_context"))
        runtime = _safe_dict(capability_view.get("runtime"))
        advisory = _safe_dict(capability_view.get("advisory_flags"))
        execution_verdict = _safe_dict(capability_view.get("execution_verdict"))
        policy_verdict = _safe_dict(capability_view.get("policy_verdict"))
        if runtime.get("enabled") is False:
            return -1000.0
        adjustment = 0.0
        if advisory.get("approval_gate_required"):
            adjustment -= 5.0
        if advisory.get("non_prod_ready"):
            adjustment -= 8.0
        if advisory.get("insufficient_evidence"):
            adjustment -= 7.0
        if advisory.get("stale_evidence"):
            adjustment -= 10.0
        if advisory.get("low_confidence"):
            adjustment -= 6.0
        if runtime.get("degraded"):
            adjustment -= 10.0
        if execution_verdict.get("approval_required"):
            adjustment -= 8.0
        if execution_verdict.get("blocked_by_policy"):
            adjustment -= 15.0
        if execution_verdict and execution_verdict.get("budget_allowed") is False:
            adjustment -= 12.0
        if execution_verdict and execution_verdict.get("blast_radius_allowed") is False:
            adjustment -= 10.0
        if policy_verdict and policy_verdict.get("allowed") is False:
            adjustment -= 25.0
        if _text(policy_verdict.get("recommended_autonomy_tier")) == "supervised":
            adjustment -= 8.0
        elif _text(policy_verdict.get("recommended_autonomy_tier")) == "bounded_autonomy":
            adjustment -= 4.0
        if runtime.get("staleness_state") == "stale":
            adjustment -= 14.0
        elif runtime.get("staleness_state") == "cooling":
            adjustment -= 5.0
        if runtime.get("evidence_state") in {"unknown", "insufficient"}:
            adjustment -= 9.0
        confidence_score = max(0.0, min(1.0, _safe_float(runtime.get("confidence_score"), default=1.0)))
        adjustment += (confidence_score - 0.5) * 6.0
        health_score = max(0.0, min(1.0, _safe_float(runtime.get("health_score"), default=1.0)))
        adjustment += (health_score - 0.5) * 10.0
        return adjustment

    def _score(self, item: GoalQueueItem) -> float:
        goal_family = self._goal_family_classifier.classify(item.goal)
        return self._policy.score(item=item, goal_family=goal_family) + self._capability_adjustment(item)

    def _enrich_long_horizon_metadata(self, *, tenant_id: str, business_id: str, goal: str, metadata: Mapping[str, Any] | None, performance_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(metadata or {})
        goal_family = payload.get("goal_family") or self._goal_family_classifier.classify(goal)
        payload["goal_family"] = goal_family
        if self._long_horizon_planner is None:
            payload.setdefault("long_horizon", {})
            return payload
        long_horizon_view = self._long_horizon_planner.build_plan(
            tenant_id=tenant_id,
            business_id=business_id,
            goal=goal,
            metadata=payload,
            performance_context=performance_context,
        )
        long_horizon_payload = long_horizon_view.to_dict()
        payload["long_horizon"] = long_horizon_payload
        payload.setdefault("planning_horizon", long_horizon_payload.get("planning_horizon"))
        payload.setdefault(
            "decomposed_focus",
            [task.get("title") for task in (long_horizon_payload.get("tasks") or []) if _text(task.get("title"))],
        )
        payload.setdefault(
            "remaining_action_hints",
            [action_type for task in (long_horizon_payload.get("tasks") or []) for action_type in (task.get("recommended_action_types") or []) if _text(action_type)][:20],
        )
        return payload

    def add_goal(self, *, tenant_id: str, business_id: str, goal_id: str, goal: str, priority: int = 50, urgency: int = 50, budget_weight: float = 1.0, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not _text(tenant_id):
            raise ValueError("tenant_id must not be empty")
        if not _text(business_id):
            raise ValueError("business_id must not be empty")
        if not _text(goal_id):
            raise ValueError("goal_id must not be empty")
        if not _text(goal):
            raise ValueError("goal must not be empty")
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id)
        queue = [item for item in snapshot.queue if item.goal_id != goal_id]
        goal_family = self._goal_family_classifier.classify(goal)
        base_metadata = dict(metadata or {})
        base_metadata["goal_family"] = goal_family
        enriched_metadata = self._enrich_long_horizon_metadata(tenant_id=tenant_id, business_id=business_id, goal=str(goal), metadata=base_metadata)
        enriched_metadata = self._strategic_planner.enrich_metadata(goal=str(goal), metadata=enriched_metadata)
        enriched_metadata["goal_family"] = goal_family
        enriched_metadata["strategy_support"] = self._policy.support(goal=goal, goal_family=goal_family, metadata=enriched_metadata)
        enriched_metadata["strategy_hints"] = [x.to_dict() for x in self._strategy_support_policy.build_hints(goal_family=goal_family, metadata=enriched_metadata)]
        queue.append(
            GoalQueueItem(
                goal_id=str(goal_id),
                goal=str(goal),
                priority=max(0, min(100, int(priority))),
                urgency=max(0, min(100, int(urgency))),
                budget_weight=max(0.0, float(budget_weight)),
                metadata=enriched_metadata,
            )
        )
        updated = MultiGoalPlanSnapshot(schema_version=MULTI_GOAL_SCHEMA_VERSION, tenant_id=str(tenant_id), business_id=str(business_id), queue=tuple(queue), active_goal_id=snapshot.active_goal_id)
        self._store.save(updated)
        return updated.to_dict()

    def update_goal_after_run(self, *, tenant_id: str, business_id: str, goal_id: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        if not _text(tenant_id):
            raise ValueError("tenant_id must not be empty")
        if not _text(business_id):
            raise ValueError("business_id must not be empty")
        if not _text(goal_id):
            raise ValueError("goal_id must not be empty")
        payload = _safe_dict(feedback)
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id)
        next_queue: list[GoalQueueItem] = []
        for item in snapshot.queue:
            if item.goal_id != goal_id:
                next_queue.append(item)
                continue
            feedback_view = self._strategic_planner.classify_feedback(feedback=payload)
            goal_eval = _safe_dict(payload.get("goal_evaluation"))
            progress = max(
                float(item.progress_score),
                _safe_float(feedback_view.get("completion_ratio"), default=item.progress_score),
                _safe_float(goal_eval.get("completion_ratio"), default=item.progress_score),
                _safe_float(payload.get("goal_score"), default=item.progress_score),
            )
            metadata = dict(item.metadata)
            metadata["replanning"] = {"next_mode": str(feedback_view.get("next_mode") or "replan"), "reason": str(feedback_view.get("reason") or "")}
            capability_view = _safe_dict(payload.get("capability") or payload.get("capability_planning"))
            if capability_view:
                if capability_view.get("capability") and not capability_view.get("runtime"):
                    metadata["capability"] = _safe_dict(capability_view.get("capability"))
                    if capability_view.get("allowed") is not None:
                        metadata["capability"]["allowed"] = bool(capability_view.get("allowed"))
                    if capability_view.get("fallback_used") is not None:
                        metadata["capability"]["fallback_used"] = bool(capability_view.get("fallback_used"))
                    if capability_view.get("reason"):
                        metadata["capability"]["reason"] = _text(capability_view.get("reason"))
                else:
                    metadata["capability"] = capability_view
                metadata["capability_replanning"] = {
                    "blocked": bool(payload.get("blocked_by_policy") or capability_view.get("allowed") is False),
                    "fallback_used": bool(payload.get("fallback_used") or _safe_dict(capability_view).get("fallback_used")),
                    "reason": _text(payload.get("reason") or payload.get("verification_status") or feedback_view.get("reason")),
                }
            metadata = self._strategic_planner.apply_feedback(metadata=metadata, feedback_view=feedback_view, feedback=payload)
            goal_family = self._goal_family_classifier.classify(item.goal)
            perf_context = _safe_dict(payload.get("performance_feedback_learning"))
            metadata = self._enrich_long_horizon_metadata(
                tenant_id=tenant_id,
                business_id=business_id,
                goal=item.goal,
                metadata=metadata,
                performance_context=perf_context or payload,
            )
            if self._long_horizon_planner is not None:
                metadata["strategy_memory"] = self._long_horizon_planner.update_memory_after_feedback(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    plan_context=metadata.get("long_horizon"),
                    feedback=payload,
                )
            metadata["strategy_hints"] = [x.to_dict() for x in self._strategy_support_policy.build_hints(goal_family=goal_family, feedback=payload, metadata=metadata)]
            next_queue.append(
                GoalQueueItem(
                    goal_id=item.goal_id,
                    goal=item.goal,
                    priority=item.priority,
                    urgency=item.urgency,
                    budget_weight=item.budget_weight,
                    status=self._policy.next_status(feedback_view=feedback_view),
                    active=not bool(feedback_view.get("achieved")),
                    blocked=bool(feedback_view.get("blocked")),
                    last_outcome=_text(goal_eval.get("reason") or feedback_view.get("reason") or payload.get("verification_status")),
                    progress_score=max(0.0, min(1.0, progress)),
                    metadata=self._strategic_planner.enrich_metadata(goal=item.goal, metadata=metadata),
                )
            )
        updated = MultiGoalPlanSnapshot(schema_version=MULTI_GOAL_SCHEMA_VERSION, tenant_id=snapshot.tenant_id, business_id=snapshot.business_id, queue=tuple(next_queue), active_goal_id=snapshot.active_goal_id)
        self._store.save(updated)
        return updated.to_dict()

    def select_next_goal(self, *, tenant_id: str, business_id: str) -> MultiGoalSelection:
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id)
        base_scores = {item.goal_id: self._score(item) for item in snapshot.queue}
        ranked, ranking_diagnostics = self._strategic_planner.rank_items(items=snapshot.queue, base_scores=base_scores)
        candidate = ranked[0] if ranked and self._score(ranked[0]) > 0.0 else None
        if candidate is not None and (candidate.blocked or not candidate.active):
            candidate = next((item for item in ranked if item.active and not item.blocked and self._score(item) > 0.0), None)
        strategic_context = self._strategic_planner.explain_selection(selected_item=candidate, ranked_items=ranked, ranking_diagnostics=ranking_diagnostics)
        normalized_reason = "highest_ranked_goal" if "highest_ranked_goal" in str(strategic_context.reason) else str(strategic_context.reason)
        selection = MultiGoalSelection(selected_goal_id=strategic_context.selected_goal_id, selected_goal=strategic_context.selected_goal, reason=normalized_reason, ranked_goal_ids=tuple(strategic_context.ranked_goal_ids))
        updated = MultiGoalPlanSnapshot(schema_version=snapshot.schema_version, tenant_id=snapshot.tenant_id, business_id=snapshot.business_id, queue=snapshot.queue, active_goal_id=selection.selected_goal_id)
        self._store.save(updated)
        return selection

    def load_context(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id)
        base_scores = {item.goal_id: self._score(item) for item in snapshot.queue}
        ranked, ranking_diagnostics = self._strategic_planner.rank_items(items=snapshot.queue, base_scores=base_scores)
        active_item = next((item for item in snapshot.queue if item.goal_id == snapshot.active_goal_id), None)
        if active_item is None and ranked:
            active_item = ranked[0]
        strategic_context = self._strategic_planner.explain_selection(selected_item=active_item, ranked_items=ranked, ranking_diagnostics=ranking_diagnostics)
        return {
            "active_goal_id": strategic_context.selected_goal_id or snapshot.active_goal_id,
            "active_goal": strategic_context.selected_goal,
            "selection_reason": ("highest_ranked_goal" if "highest_ranked_goal" in str(strategic_context.reason) else str(strategic_context.reason)),
            "queue": [self._strategic_planner.build_record(item=item).to_dict() for item in snapshot.queue],
            "planning_horizon": strategic_context.planning_horizon,
            "decomposed_focus": list(strategic_context.decomposed_focus),
            "long_horizon": _safe_dict(getattr(active_item, "metadata", {}).get("long_horizon")) if active_item is not None else {},
            "deferred_goal_ids": list(strategic_context.deferred_goal_ids),
            "blocked_goal_ids": list(strategic_context.blocked_goal_ids),
            "ranked_goal_ids": list(strategic_context.ranked_goal_ids),
            "strategy_diagnostics": dict(strategic_context.diagnostics),
            "planning_memory_summary": dict(strategic_context.planning_memory_summary),
            "must_not_issue_decision": True,
            "evidence_only": True,
        }


__all__ = [
    "CANON_MULTI_GOAL_PLANNER",
    "FileMultiGoalPlannerStore",
    "GoalQueueItem",
    "MultiGoalPlanSnapshot",
    "MultiGoalPlannerService",
    "MultiGoalSelection",
]
