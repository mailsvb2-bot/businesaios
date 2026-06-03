from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Mapping

CANON_GOAL_PLAN_MEMORY = True
GOAL_PLAN_SCHEMA_VERSION = 1


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_key(value: object, *, fallback: str) -> str:
    token = _text(value)
    if not token:
        return fallback
    return token.replace("\\", "_").replace("/", "_").replace(":", "_").replace(" ", "_")


@dataclass(frozen=True)
class GoalPlanStepRecord:
    step_index: int
    action_type: str
    status: str
    verified: bool = False
    goal_reached: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoalPlanSnapshot:
    schema_version: int = GOAL_PLAN_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    goal: str = ""
    plan_id: str = ""
    plan_status: str = "open"
    horizon: str = "multi_step"
    next_focus: str | None = None
    completed_steps: tuple[GoalPlanStepRecord, ...] = ()
    remaining_action_hints: tuple[str, ...] = ()
    last_feedback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "goal": str(self.goal),
            "plan_id": str(self.plan_id),
            "plan_status": str(self.plan_status),
            "horizon": str(self.horizon),
            "next_focus": self.next_focus,
            "completed_steps": [asdict(item) for item in self.completed_steps],
            "remaining_action_hints": list(self.remaining_action_hints),
            "last_feedback": dict(self.last_feedback),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GoalPlanSnapshot:
        completed_steps = []
        for item in payload.get("completed_steps") or []:
            row = _safe_dict(item)
            completed_steps.append(
                GoalPlanStepRecord(
                    step_index=_safe_int(row.get("step_index")),
                    action_type=_text(row.get("action_type")),
                    status=_text(row.get("status")),
                    verified=bool(row.get("verified")),
                    goal_reached=bool(row.get("goal_reached")),
                    notes=tuple(str(x) for x in row.get("notes") or [] if str(x).strip()),
                )
            )
        return cls(
            schema_version=_safe_int(payload.get("schema_version"), default=GOAL_PLAN_SCHEMA_VERSION),
            tenant_id=_text(payload.get("tenant_id")),
            business_id=_text(payload.get("business_id")),
            goal=_text(payload.get("goal")),
            plan_id=_text(payload.get("plan_id")),
            plan_status=_text(payload.get("plan_status") or "open") or "open",
            horizon=_text(payload.get("horizon") or "multi_step") or "multi_step",
            next_focus=_text(payload.get("next_focus")) or None,
            completed_steps=tuple(completed_steps),
            remaining_action_hints=tuple(str(x) for x in payload.get("remaining_action_hints") or [] if str(x).strip()),
            last_feedback=dict(_safe_dict(payload.get("last_feedback"))),
        )


class FileGoalPlanMemoryStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, business_id: str, goal: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback="default") / f"{_safe_key(business_id, fallback='business')}__{_safe_key(goal, fallback='goal')}.json"

    def load(self, *, tenant_id: str, business_id: str, goal: str) -> GoalPlanSnapshot:
        path = self._path(tenant_id=tenant_id, business_id=business_id, goal=goal)
        if not path.exists():
            return GoalPlanSnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal=str(goal), plan_id=f"{_safe_key(tenant_id, fallback='default')}:{_safe_key(business_id, fallback='business')}:{_safe_key(goal, fallback='goal')}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return GoalPlanSnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal=str(goal), plan_id=f"{_safe_key(tenant_id, fallback='default')}:{_safe_key(business_id, fallback='business')}:{_safe_key(goal, fallback='goal')}")
        return GoalPlanSnapshot.from_dict(payload)

    def save(self, snapshot: GoalPlanSnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id, goal=snapshot.goal)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix=".goal_plan_", suffix=".json", dir=str(path.parent))
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


class GoalPlanMemoryService:
    def __init__(self, *, store: FileGoalPlanMemoryStore) -> None:
        self._store = store

    def load_context(self, *, tenant_id: str, business_id: str, goal: str) -> dict[str, Any]:
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id, goal=goal)
        return {
            "plan_id": snapshot.plan_id,
            "plan_status": snapshot.plan_status,
            "horizon": snapshot.horizon,
            "next_focus": snapshot.next_focus,
            "remaining_action_hints": list(snapshot.remaining_action_hints),
            "completed_steps": [asdict(item) for item in snapshot.completed_steps],
            "must_not_issue_decision": True,
        }

    def update_after_step(self, *, tenant_id: str, business_id: str, goal: str, step_index: int, action_type: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id, goal=goal)
        data = _safe_dict(feedback)
        notes: list[str] = []
        if data.get("goal_evaluation"):
            notes.append("goal_evaluation")
        if data.get("capability_planning"):
            notes.append("capability_planning")
        if data.get("self_healing_retry"):
            notes.append("self_healing_retry")
        completed_steps = list(snapshot.completed_steps)
        completed_steps.append(
            GoalPlanStepRecord(
                step_index=int(step_index),
                action_type=str(action_type),
                status=str(data.get("verification_status") or data.get("status") or "unknown"),
                verified=bool(data.get("verified")),
                goal_reached=bool(data.get("goal_reached")),
                notes=tuple(notes),
            )
        )
        next_focus = None
        remaining_hints = list(snapshot.remaining_action_hints)
        if remaining_hints:
            remaining_hints = remaining_hints[1:]
        recovery = _safe_dict(data.get("self_healing_retry"))
        goal_eval = _safe_dict(data.get("goal_evaluation"))
        goal_achieved = bool(data.get("goal_reached") or goal_eval.get("achieved"))
        if recovery.get("fallback_action_type"):
            next_focus = str(recovery.get("fallback_action_type"))
            remaining_hints.insert(0, next_focus)
        elif goal_achieved:
            next_focus = None
            remaining_hints = []
        elif not remaining_hints:
            next_focus = str(action_type)
            remaining_hints = [next_focus]
        updated = GoalPlanSnapshot(
            schema_version=GOAL_PLAN_SCHEMA_VERSION,
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            goal=str(goal),
            plan_id=snapshot.plan_id,
            plan_status="completed" if goal_achieved else "open",
            horizon=snapshot.horizon,
            next_focus=next_focus,
            completed_steps=tuple(completed_steps[-50:]),
            remaining_action_hints=tuple(remaining_hints[:20]),
            last_feedback=dict(data),
        )
        self._store.save(updated)
        return self.load_context(tenant_id=tenant_id, business_id=business_id, goal=goal)


__all__ = [
    "CANON_GOAL_PLAN_MEMORY",
    "FileGoalPlanMemoryStore",
    "GOAL_PLAN_SCHEMA_VERSION",
    "GoalPlanMemoryService",
    "GoalPlanSnapshot",
    "GoalPlanStepRecord",
]
