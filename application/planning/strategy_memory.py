from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

CANON_STRATEGY_MEMORY = True
STRATEGY_MEMORY_SCHEMA_VERSION = 1
_ALLOWED_HORIZONS = frozenset({"day", "week", "month", "quarter"})


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def _normalize_horizon(value: object, *, default: str = "week") -> str:
    token = _text(value).lower() or default
    return token if token in _ALLOWED_HORIZONS else default


@dataclass(frozen=True)
class StrategyPatternStat:
    key: str
    observed_runs: int = 0
    successful_runs: int = 0
    verified_runs: int = 0
    avg_completion_ratio: float = 0.0
    avg_cost_efficiency: float = 0.0
    typical_step_count: int = 1
    last_signal: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StrategyPatternStat":
        return cls(
            key=_text(payload.get("key")),
            observed_runs=max(0, _safe_int(payload.get("observed_runs"))),
            successful_runs=max(0, _safe_int(payload.get("successful_runs"))),
            verified_runs=max(0, _safe_int(payload.get("verified_runs"))),
            avg_completion_ratio=max(0.0, min(1.0, _safe_float(payload.get("avg_completion_ratio")))),
            avg_cost_efficiency=max(0.0, min(1.0, _safe_float(payload.get("avg_cost_efficiency")))),
            typical_step_count=max(1, _safe_int(payload.get("typical_step_count"), default=1)),
            last_signal=_text(payload.get("last_signal")),
        )


@dataclass(frozen=True)
class StrategyMemorySnapshot:
    schema_version: int = STRATEGY_MEMORY_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    goal_family: str = "default"
    preferred_horizon: str = "week"
    observed_runs: int = 0
    verified_runs: int = 0
    successful_runs: int = 0
    risk_flags: tuple[str, ...] = ()
    decomposition_patterns: dict[str, StrategyPatternStat] = field(default_factory=dict)
    task_patterns: dict[str, StrategyPatternStat] = field(default_factory=dict)
    last_compact_feedback: dict[str, Any] = field(default_factory=dict)
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "goal_family": self.goal_family,
            "preferred_horizon": self.preferred_horizon,
            "observed_runs": int(self.observed_runs),
            "verified_runs": int(self.verified_runs),
            "successful_runs": int(self.successful_runs),
            "risk_flags": list(self.risk_flags),
            "decomposition_patterns": {key: value.to_dict() for key, value in self.decomposition_patterns.items()},
            "task_patterns": {key: value.to_dict() for key, value in self.task_patterns.items()},
            "last_compact_feedback": dict(self.last_compact_feedback),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StrategyMemorySnapshot":
        def _load_stats(value: object) -> dict[str, StrategyPatternStat]:
            raw = _safe_dict(value)
            return {str(key): StrategyPatternStat.from_dict(_safe_dict(item)) for key, item in raw.items() if _text(key)}
        return cls(
            schema_version=max(1, _safe_int(payload.get("schema_version"), default=STRATEGY_MEMORY_SCHEMA_VERSION)),
            tenant_id=_text(payload.get("tenant_id")),
            business_id=_text(payload.get("business_id")),
            goal_family=_text(payload.get("goal_family") or "default") or "default",
            preferred_horizon=_normalize_horizon(payload.get("preferred_horizon") or "week"),
            observed_runs=max(0, _safe_int(payload.get("observed_runs"))),
            verified_runs=max(0, _safe_int(payload.get("verified_runs"))),
            successful_runs=max(0, _safe_int(payload.get("successful_runs"))),
            risk_flags=tuple(str(x) for x in (payload.get("risk_flags") or ()) if _text(x)),
            decomposition_patterns=_load_stats(payload.get("decomposition_patterns")),
            task_patterns=_load_stats(payload.get("task_patterns")),
            last_compact_feedback=dict(_safe_dict(payload.get("last_compact_feedback"))),
        )


class FileStrategyMemoryStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, business_id: str, goal_family: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback="default") / f"{_safe_key(business_id, fallback='business')}__{_safe_key(goal_family, fallback='default')}.json"

    def load(self, *, tenant_id: str, business_id: str, goal_family: str) -> StrategyMemorySnapshot:
        path = self._path(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)
        if not path.exists():
            return StrategyMemorySnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal_family=str(goal_family or "default") or "default")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return StrategyMemorySnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal_family=str(goal_family or "default") or "default")
        return StrategyMemorySnapshot.from_dict(payload)

    def save(self, snapshot: StrategyMemorySnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id, goal_family=snapshot.goal_family)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix=".strategy_memory_", suffix=".json", dir=str(path.parent))
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


class StrategyMemoryService:
    MAX_RISK_FLAGS = 12
    MAX_COMPACT_KEYS = 12

    def __init__(self, *, store: FileStrategyMemoryStore) -> None:
        self._store = store

    def load_context(self, *, tenant_id: str, business_id: str, goal_family: str) -> dict[str, Any]:
        return self._store.load(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family).to_dict()

    def _compact_feedback(self, *, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = _safe_dict(feedback)
        goal_eval = _safe_dict(payload.get("goal_evaluation"))
        perf = _safe_dict(payload.get("performance_feedback_learning"))
        long_horizon = _safe_dict(perf.get("long_horizon_signals"))
        compact = {
            "verification_status": _text(payload.get("verification_status")),
            "verified": bool(payload.get("verified")),
            "blocked_by_policy": bool(payload.get("blocked_by_policy")),
            "approval_required": bool(payload.get("approval_required")),
            "goal_achieved": bool(goal_eval.get("achieved") or payload.get("goal_reached")),
            "completion_ratio": max(0.0, min(1.0, _safe_float(goal_eval.get("completion_ratio"), default=payload.get("goal_score") or 0.0))),
            "checkpoint_readiness": _text(long_horizon.get("checkpoint_readiness")),
            "preferred_planning_horizon": _normalize_horizon(perf.get("preferred_planning_horizon") or "week"),
            "cost_efficiency_score": max(0.0, min(1.0, _safe_float(perf.get("cost_efficiency_score"), default=0.0))),
        }
        return {key: value for key, value in compact.items() if value not in ("", None)}

    def _update_stat(self, current: StrategyPatternStat | None, *, key: str, succeeded: bool, verified: bool, completion_ratio: float, cost_efficiency: float, typical_step_count: int, signal: str) -> StrategyPatternStat:
        base = current or StrategyPatternStat(key=key)
        observed_runs = base.observed_runs + 1
        return StrategyPatternStat(
            key=key,
            observed_runs=observed_runs,
            successful_runs=base.successful_runs + int(succeeded),
            verified_runs=base.verified_runs + int(verified),
            avg_completion_ratio=((base.avg_completion_ratio * base.observed_runs) + completion_ratio) / observed_runs,
            avg_cost_efficiency=((base.avg_cost_efficiency * base.observed_runs) + cost_efficiency) / observed_runs,
            typical_step_count=max(1, int(round(((base.typical_step_count * base.observed_runs) + typical_step_count) / observed_runs))),
            last_signal=signal,
        )

    def update_after_feedback(self, *, tenant_id: str, business_id: str, goal_family: str, plan_context: Mapping[str, Any] | None, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)
        plan = _safe_dict(plan_context)
        compact = self._compact_feedback(feedback=feedback)
        succeeded = bool(compact.get("goal_achieved"))
        verified = bool(compact.get("verified")) or _text(compact.get("verification_status")).lower() == "verified"
        completion_ratio = max(0.0, min(1.0, _safe_float(compact.get("completion_ratio"), default=0.0)))
        cost_efficiency = max(0.0, min(1.0, _safe_float(compact.get("cost_efficiency_score"), default=0.0)))
        signal = _text(compact.get("verification_status") or compact.get("checkpoint_readiness") or "feedback")
        preferred_horizon = _normalize_horizon(compact.get("preferred_planning_horizon") or plan.get("planning_horizon") or snapshot.preferred_horizon or "week")

        risk_flags = list(snapshot.risk_flags)
        if compact.get("blocked_by_policy") and "policy_blocked" not in risk_flags:
            risk_flags.append("policy_blocked")
        if compact.get("approval_required") and "approval_required" not in risk_flags:
            risk_flags.append("approval_required")
        if not verified and completion_ratio == 0.0 and "weak_verification" not in risk_flags:
            risk_flags.append("weak_verification")
        checkpoint_readiness = _text(compact.get("checkpoint_readiness"))
        if checkpoint_readiness and checkpoint_readiness not in risk_flags:
            risk_flags.append(checkpoint_readiness)

        decomposition_patterns = dict(snapshot.decomposition_patterns)
        task_patterns = dict(snapshot.task_patterns)
        tasks = plan.get("tasks") or ()
        task_count = len(tasks) if isinstance(tasks, (list, tuple)) else 1
        for task in tasks if isinstance(tasks, (list, tuple)) else ():
            row = _safe_dict(task)
            phase = _text(row.get("phase"))
            task_id = _text(row.get("task_id"))
            estimated_steps = max(1, _safe_int(row.get("estimated_steps"), default=1))
            if phase:
                decomposition_patterns[phase] = self._update_stat(decomposition_patterns.get(phase), key=phase, succeeded=succeeded, verified=verified, completion_ratio=completion_ratio, cost_efficiency=cost_efficiency, typical_step_count=task_count, signal=signal)
            if task_id:
                task_patterns[task_id] = self._update_stat(task_patterns.get(task_id), key=task_id, succeeded=succeeded, verified=verified, completion_ratio=completion_ratio, cost_efficiency=cost_efficiency, typical_step_count=estimated_steps, signal=signal)

        updated = StrategyMemorySnapshot(
            schema_version=STRATEGY_MEMORY_SCHEMA_VERSION,
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            goal_family=str(goal_family or "default") or "default",
            preferred_horizon=preferred_horizon,
            observed_runs=snapshot.observed_runs + 1,
            verified_runs=snapshot.verified_runs + int(verified),
            successful_runs=snapshot.successful_runs + int(succeeded),
            risk_flags=tuple(dict.fromkeys(risk_flags))[:self.MAX_RISK_FLAGS],
            decomposition_patterns=decomposition_patterns,
            task_patterns=task_patterns,
            last_compact_feedback=dict(list(compact.items())[: self.MAX_COMPACT_KEYS]),
        )
        self._store.save(updated)
        return updated.to_dict()


__all__ = [
    "CANON_STRATEGY_MEMORY",
    "FileStrategyMemoryStore",
    "STRATEGY_MEMORY_SCHEMA_VERSION",
    "StrategyMemoryService",
    "StrategyMemorySnapshot",
    "StrategyPatternStat",
]
