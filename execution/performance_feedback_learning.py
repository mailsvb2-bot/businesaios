from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from runtime.service_names import RuntimeServiceName

from execution.goal_family_classifier import GoalFamilyClassifier
from execution.performance_feedback_policy import PerformanceFeedbackPolicy
from execution.runtime_keys import ACTION_BUDGET_KEY
from config.risk_evaluation_policy import DEFAULT_PERFORMANCE_FEEDBACK_LEARNING_POLICY


CANON_PERFORMANCE_FEEDBACK_LEARNING = True
PERFORMANCE_FEEDBACK_SCHEMA_VERSION = 1
_ALLOWED_HORIZONS = frozenset({"day", "week", "month", "quarter"})
_MAX_RECENT_SIGNALS = 20
_MAX_SIGNAL_LENGTH = 96


def _bounded_signal(value: object) -> str:
    token = _text(value)
    if not token:
        return ""
    if len(token) <= _MAX_SIGNAL_LENGTH:
        return token
    return token[: _MAX_SIGNAL_LENGTH - 3].rstrip() + "..."


def _append_signal(target: list[str], value: object) -> None:
    token = _bounded_signal(value)
    if token:
        target.append(token)



def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


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


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _dedupe_tail(values: list[str], *, limit: int) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in reversed(values):
        token = _text(raw)
        if not token:
            continue
        marker = token.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(token)
        if len(ordered) >= max(1, int(limit)):
            break
    ordered.reverse()
    return tuple(ordered)


def _safe_retry_feedback(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = _safe_dict(payload.get("self_healing_retry"))
    if not value:
        return {}
    return {
        "reason": _bounded_signal(value.get("reason")),
        "should_open_operator_handoff": _safe_bool(value.get("should_open_operator_handoff")),
        "should_quarantine_capability": _safe_bool(value.get("should_quarantine_capability")),
        "cooldown_seconds": max(0, _safe_int(value.get("cooldown_seconds"))),
        "recovery_mode": _bounded_signal(value.get("recovery_mode")),
        "error_family": _bounded_signal(value.get("error_family")),
    }


@dataclass(frozen=True)
class PerformanceCounters:
    total_steps: int = 0
    executed_steps: int = 0
    verified_steps: int = 0
    achieved_steps: int = 0
    blocked_steps: int = 0
    failed_steps: int = 0
    total_cost: float = 0.0
    total_budget_delta: float = 0.0
    total_outbound: int = 0
    total_publications: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PerformanceCounters":
        return cls(
            total_steps=max(0, _safe_int(payload.get("total_steps"))),
            executed_steps=max(0, _safe_int(payload.get("executed_steps"))),
            verified_steps=max(0, _safe_int(payload.get("verified_steps"))),
            achieved_steps=max(0, _safe_int(payload.get("achieved_steps"))),
            blocked_steps=max(0, _safe_int(payload.get("blocked_steps"))),
            failed_steps=max(0, _safe_int(payload.get("failed_steps"))),
            total_cost=max(0.0, _safe_float(payload.get("total_cost"))),
            total_budget_delta=max(0.0, _safe_float(payload.get("total_budget_delta"))),
            total_outbound=max(0, _safe_int(payload.get("total_outbound"))),
            total_publications=max(0, _safe_int(payload.get("total_publications"))),
        )


@dataclass(frozen=True)
class PerformanceLearningSnapshot:
    schema_version: int = PERFORMANCE_FEEDBACK_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    goal_family: str = "default"
    counters: PerformanceCounters = field(default_factory=PerformanceCounters)
    execution_success_rate: float = 0.0
    verification_rate: float = 0.0
    goal_achievement_rate: float = 0.0
    cost_efficiency_score: float = 0.0
    recommended_budget_posture: str = "neutral"
    budget_posture_detail: dict[str, Any] = field(default_factory=dict)
    recent_signals: tuple[str, ...] = ()
    preferred_planning_horizon: str = "week"
    long_horizon_signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "goal_family": str(self.goal_family),
            "counters": self.counters.to_dict(),
            "execution_success_rate": float(self.execution_success_rate),
            "verification_rate": float(self.verification_rate),
            "goal_achievement_rate": float(self.goal_achievement_rate),
            "cost_efficiency_score": float(self.cost_efficiency_score),
            "recommended_budget_posture": str(self.recommended_budget_posture),
            "budget_posture_detail": dict(self.budget_posture_detail),
            "recent_signals": list(self.recent_signals),
            "preferred_planning_horizon": str(self.preferred_planning_horizon),
            "long_horizon_signals": dict(self.long_horizon_signals),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PerformanceLearningSnapshot":
        return cls(
            schema_version=max(1, _safe_int(payload.get("schema_version"), default=PERFORMANCE_FEEDBACK_SCHEMA_VERSION)),
            tenant_id=_text(payload.get("tenant_id")),
            business_id=_text(payload.get("business_id")),
            goal_family=_text(payload.get("goal_family") or "default") or "default",
            counters=PerformanceCounters.from_dict(_safe_dict(payload.get("counters"))),
            execution_success_rate=_clamp_unit(_safe_float(payload.get("execution_success_rate"))),
            verification_rate=_clamp_unit(_safe_float(payload.get("verification_rate"))),
            goal_achievement_rate=_clamp_unit(_safe_float(payload.get("goal_achievement_rate"))),
            cost_efficiency_score=_clamp_unit(_safe_float(payload.get("cost_efficiency_score"))),
            recommended_budget_posture=_text(payload.get("recommended_budget_posture") or "neutral") or "neutral",
            budget_posture_detail=dict(_safe_dict(payload.get("budget_posture_detail"))),
            recent_signals=tuple(str(x) for x in (payload.get("recent_signals") or []) if str(x).strip()),
            preferred_planning_horizon=_normalize_horizon(payload.get("preferred_planning_horizon") or "week"),
            long_horizon_signals=dict(_safe_dict(payload.get("long_horizon_signals"))),
        )


class FilePerformanceFeedbackStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, business_id: str, goal_family: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback="default") / f"{_safe_key(business_id, fallback='business')}__{_safe_key(goal_family, fallback='default')}.json"

    def load(self, *, tenant_id: str, business_id: str, goal_family: str) -> PerformanceLearningSnapshot:
        path = self._path(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)
        if not path.exists():
            return PerformanceLearningSnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal_family=str(goal_family))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return PerformanceLearningSnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal_family=str(goal_family))
        return PerformanceLearningSnapshot.from_dict(payload)

    def save(self, snapshot: PerformanceLearningSnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id, goal_family=snapshot.goal_family)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix=".performance_", suffix=".json", dir=str(path.parent))
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


class PerformanceFeedbackLearningService:
    def __init__(self, *, store: FilePerformanceFeedbackStore, goal_family_classifier: GoalFamilyClassifier | None = None, policy: PerformanceFeedbackPolicy | None = None) -> None:
        self._store = store
        self._goal_family_classifier = goal_family_classifier or GoalFamilyClassifier()
        self._policy = policy or PerformanceFeedbackPolicy()

    def _goal_family(self, goal: str) -> str:
        return self._goal_family_classifier.classify(goal)

    def load_context(self, *, tenant_id: str, business_id: str, goal: str) -> dict[str, Any]:
        goal_family = self._goal_family(goal)
        snapshot = self._store.load(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)
        return {
            "goal_family": snapshot.goal_family,
            "execution_success_rate": snapshot.execution_success_rate,
            "verification_rate": snapshot.verification_rate,
            "goal_achievement_rate": snapshot.goal_achievement_rate,
            "cost_efficiency_score": snapshot.cost_efficiency_score,
            "recommended_budget_posture": snapshot.recommended_budget_posture,
            "budget_posture_detail": dict(snapshot.budget_posture_detail),
            "recent_signals": list(snapshot.recent_signals),
            "preferred_planning_horizon": snapshot.preferred_planning_horizon,
            "long_horizon_signals": dict(snapshot.long_horizon_signals),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }

    def _preferred_horizon(self, *, verification_rate: float, goal_achievement_rate: float, cost_efficiency_score: float, blocked: bool) -> str:
        policy = DEFAULT_PERFORMANCE_FEEDBACK_LEARNING_POLICY
        if blocked or verification_rate < policy.blocked_verification_floor:
            return "day"
        if goal_achievement_rate >= policy.month_goal_achievement_threshold and verification_rate >= policy.month_verification_threshold and cost_efficiency_score >= policy.month_cost_efficiency_threshold:
            return "month"
        if goal_achievement_rate >= policy.week_goal_achievement_threshold and verification_rate >= policy.week_verification_threshold:
            return "week"
        return "day"

    def _long_horizon_signals(self, *, payload: Mapping[str, Any], policy_view: Any) -> dict[str, Any]:
        goal_eval = _safe_dict(payload.get("goal_evaluation"))
        capability = _safe_dict(payload.get("capability") or payload.get("capability_planning"))
        completion_ratio = max(0.0, min(1.0, _safe_float(goal_eval.get("completion_ratio"), default=payload.get("goal_score") or 0.0)))
        blocked = bool(payload.get("blocked_by_policy") or payload.get("approval_required"))
        fallback_used = bool(payload.get("fallback_used") or capability.get("fallback_used"))
        verified = bool(payload.get("verified")) or _text(payload.get("verification_status")).lower() == "verified"
        policy = DEFAULT_PERFORMANCE_FEEDBACK_LEARNING_POLICY
        checkpoint_readiness = "high"
        if blocked or completion_ratio <= 0.0:
            checkpoint_readiness = "replan_now"
        elif not verified and policy_view.verification_rate < policy.checkpoint_verify_before_scale_threshold:
            checkpoint_readiness = "verify_before_scale"
        elif fallback_used:
            checkpoint_readiness = "stabilize_route"
        return {
            "checkpoint_readiness": checkpoint_readiness,
            "completion_ratio": completion_ratio,
            "fallback_used": fallback_used,
            "blocked": blocked,
            "verified": verified,
            "evidence_only": True,
            "must_not_issue_decision": True,
        }

    def update_after_step(self, *, tenant_id: str, business_id: str, goal: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        goal_family = self._goal_family(goal)
        current = self._store.load(tenant_id=tenant_id, business_id=business_id, goal_family=goal_family)
        payload = _safe_dict(feedback)
        action_budget = _safe_dict(payload.get(ACTION_BUDGET_KEY) or payload.get(RuntimeServiceName.ACTION_BUDGET))
        budget_state = _safe_dict(action_budget.get("snapshot_after"))

        counters = current.counters
        next_counters = PerformanceCounters(
            total_steps=counters.total_steps + 1,
            executed_steps=counters.executed_steps + int(bool(payload.get("executed"))),
            verified_steps=counters.verified_steps + int(bool(payload.get("verified"))),
            achieved_steps=counters.achieved_steps + int(bool(_safe_dict(payload.get("goal_evaluation")).get("achieved") or payload.get("goal_reached"))),
            blocked_steps=counters.blocked_steps + int(bool(payload.get("blocked_by_policy") or payload.get("approval_required"))),
            failed_steps=counters.failed_steps + int(bool(payload.get("executed") is False and not payload.get("blocked_by_policy") and not payload.get("approval_required"))),
            total_cost=max(counters.total_cost, _safe_float(budget_state.get("spent_total"), default=counters.total_cost)),
            total_budget_delta=max(counters.total_budget_delta, _safe_float(budget_state.get("budget_change_total"), default=counters.total_budget_delta)),
            total_outbound=max(counters.total_outbound, _safe_int(budget_state.get("outbound_total"), default=counters.total_outbound)),
            total_publications=max(counters.total_publications, _safe_int(budget_state.get("publications_total"), default=counters.total_publications)),
        )
        policy_view = self._policy.build_view(counters=next_counters.to_dict(), spent_total=next_counters.total_cost)
        preferred_planning_horizon = self._preferred_horizon(
            verification_rate=policy_view.verification_rate,
            goal_achievement_rate=policy_view.goal_achievement_rate,
            cost_efficiency_score=policy_view.cost_efficiency_score,
            blocked=bool(payload.get("blocked_by_policy") or payload.get("approval_required")),
        )
        long_horizon_signals = self._long_horizon_signals(payload=payload, policy_view=policy_view)

        recent_signals = list(current.recent_signals)
        for signal in policy_view.recent_signals:
            _append_signal(recent_signals, signal)
        if payload.get("verified"):
            _append_signal(recent_signals, "verified")
        if _safe_dict(payload.get("goal_evaluation")).get("achieved") or payload.get("goal_reached"):
            _append_signal(recent_signals, "goal_achieved")
        if payload.get("blocked_by_policy") or payload.get("approval_required"):
            _append_signal(recent_signals, "blocked")
        retry_feedback = _safe_retry_feedback(payload)
        if retry_feedback:
            _append_signal(recent_signals, "retry_observed")
            if retry_feedback.get("reason"):
                _append_signal(recent_signals, f"retry:{retry_feedback['reason']}")
            if retry_feedback.get("error_family"):
                _append_signal(recent_signals, f"retry_family:{retry_feedback['error_family']}")
            if retry_feedback.get("recovery_mode"):
                _append_signal(recent_signals, f"retry_mode:{retry_feedback['recovery_mode']}")
            if retry_feedback.get("cooldown_seconds"):
                _append_signal(recent_signals, "retry_cooldown")
            if retry_feedback.get("should_open_operator_handoff"):
                _append_signal(recent_signals, "retry_operator_handoff")
            if retry_feedback.get("should_quarantine_capability"):
                _append_signal(recent_signals, "retry_quarantine_signal")
        if long_horizon_signals.get("checkpoint_readiness"):
            _append_signal(recent_signals, long_horizon_signals["checkpoint_readiness"])
        recent_signals = list(_dedupe_tail(recent_signals, limit=_MAX_RECENT_SIGNALS))

        next_snapshot = PerformanceLearningSnapshot(
            schema_version=PERFORMANCE_FEEDBACK_SCHEMA_VERSION,
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            goal_family=goal_family,
            counters=next_counters,
            execution_success_rate=policy_view.execution_success_rate,
            verification_rate=policy_view.verification_rate,
            goal_achievement_rate=policy_view.goal_achievement_rate,
            cost_efficiency_score=policy_view.cost_efficiency_score,
            recommended_budget_posture=policy_view.budget_posture.posture,
            budget_posture_detail=policy_view.budget_posture.to_dict(),
            recent_signals=tuple(recent_signals),
            preferred_planning_horizon=preferred_planning_horizon,
            long_horizon_signals=long_horizon_signals,
        )
        self._store.save(next_snapshot)
        return self.load_context(tenant_id=tenant_id, business_id=business_id, goal=goal)


__all__ = [
    "CANON_PERFORMANCE_FEEDBACK_LEARNING",
    "FilePerformanceFeedbackStore",
    "PerformanceCounters",
    "PerformanceFeedbackLearningService",
    "PerformanceLearningSnapshot",
]
