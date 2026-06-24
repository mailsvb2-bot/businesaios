from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Mapping
from config.decision_safety_policy import DEFAULT_GOAL_DECOMPOSITION_POLICY


CANON_GOAL_DECOMPOSITION_ENGINE = True
GOAL_DECOMPOSITION_SCHEMA_VERSION = 1
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


def _slug(value: object, *, fallback: str) -> str:
    token = _text(value).lower()
    if not token:
        return fallback
    chars: list[str] = []
    last_sep = False
    for ch in token:
        if ch.isalnum():
            chars.append(ch)
            last_sep = False
        elif ch in {" ", "-", "_", "/", ":"}:
            if not last_sep:
                chars.append("_")
                last_sep = True
    normalized = "".join(chars).strip("_")
    return normalized or fallback


def _normalize_horizon(value: object, *, default: str = "week") -> str:
    token = _text(value).lower() or default
    return token if token in _ALLOWED_HORIZONS else default


@dataclass(frozen=True)
class GoalDecompositionTask:
    task_id: str
    title: str
    phase: str
    depends_on: tuple[str, ...] = ()
    success_metric: str = ""
    evidence_hint: str = ""
    recommended_action_types: tuple[str, ...] = ()
    estimated_steps: int = 1
    priority_weight: float = 1.0
    checkpoint_required: bool = True
    parallelizable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["depends_on"] = list(self.depends_on)
        payload["recommended_action_types"] = list(self.recommended_action_types)
        return payload


@dataclass(frozen=True)
class GoalDecompositionResult:
    schema_version: int = GOAL_DECOMPOSITION_SCHEMA_VERSION
    goal_family: str = "default"
    planning_horizon: str = "week"
    decomposition_reason: str = "goal_family_template"
    decomposition_version: str = "v1"
    decomposition_id: str = ""
    total_estimated_steps: int = 0
    checkpoint_every_steps: int = 1
    tasks: tuple[GoalDecompositionTask, ...] = ()
    success_metrics: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "goal_family": self.goal_family,
            "planning_horizon": self.planning_horizon,
            "decomposition_reason": self.decomposition_reason,
            "decomposition_version": self.decomposition_version,
            "decomposition_id": self.decomposition_id,
            "total_estimated_steps": int(self.total_estimated_steps),
            "checkpoint_every_steps": int(self.checkpoint_every_steps),
            "tasks": [task.to_dict() for task in self.tasks],
            "success_metrics": list(self.success_metrics),
            "risk_flags": list(self.risk_flags),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


class GoalDecompositionEngine:
    """Evidence-only long-horizon decomposition owner.

    This component never chooses the final action and never executes side effects.
    It only prepares a durable phase/task/checkpoint structure that can be carried
    inside metadata for the canonical planning and decision path.
    """

    def detect_goal_family(self, *, goal: str, metadata: Mapping[str, Any] | None = None) -> str:
        payload = _safe_dict(metadata)
        explicit = _text(payload.get("goal_family"))
        if explicit:
            return explicit
        policy = DEFAULT_GOAL_DECOMPOSITION_POLICY
        text = goal.lower()
        if any(token in text for token in policy.retention_keywords):
            return "retention"
        if any(token in text for token in policy.reputation_keywords):
            return "reputation"
        if any(token in text for token in policy.demand_generation_keywords):
            return "demand_generation"
        if any(token in text for token in policy.revenue_growth_keywords):
            return "revenue_growth"
        return "default"

    def _default_template(self, *, goal_family: str) -> tuple[dict[str, Any], ...]:
        policy = DEFAULT_GOAL_DECOMPOSITION_POLICY
        if goal_family == "revenue_growth":
            return (
                {"phase": "diagnose", "title": "Assess demand, offer friction, and conversion bottlenecks", "success_metric": "baseline_captured", "evidence_hint": "baseline_state", "recommended_action_types": ("assess_state",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "activate", "title": "Launch or adjust the highest-confidence demand action", "success_metric": "qualified_pipeline_created", "evidence_hint": "execution_receipt", "recommended_action_types": ("launch_campaign", "publish_offer"), "estimated_steps": 2, "priority_weight": policy.activation_priority_weight, "checkpoint_required": True},
                {"phase": "verify", "title": "Verify conversion and revenue movement", "success_metric": "verified_revenue_delta", "evidence_hint": "revenue_verification", "recommended_action_types": ("verify_conversion",), "estimated_steps": 1, "priority_weight": policy.verification_priority_weight, "checkpoint_required": True},
                {"phase": "scale", "title": "Scale only if verified economics stay healthy", "success_metric": "efficient_scale_candidate", "evidence_hint": "economic_signal", "recommended_action_types": ("tune_budget", "expand_channel"), "estimated_steps": 2, "priority_weight": policy.scale_priority_weight, "checkpoint_required": True},
            )
        if goal_family == "retention":
            return (
                {"phase": "segment", "title": "Identify churn-risk or dormant cohorts", "success_metric": "target_cohort_selected", "evidence_hint": "cohort_snapshot", "recommended_action_types": ("segment_customers",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "engage", "title": "Run retention touchpoint for the selected cohort", "success_metric": "outreach_delivered", "evidence_hint": "delivery_receipt", "recommended_action_types": ("send_followup", "send_offer"), "estimated_steps": 2, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "verify", "title": "Verify repeat behavior or reactivation", "success_metric": "repeat_rate_verified", "evidence_hint": "retention_measurement", "recommended_action_types": ("measure_repeat_rate",), "estimated_steps": 1, "priority_weight": policy.verification_priority_weight, "checkpoint_required": True},
            )
        if goal_family == "reputation":
            return (
                {"phase": "target", "title": "Select the best review request audience", "success_metric": "review_candidates_prepared", "evidence_hint": "audience_snapshot", "recommended_action_types": ("select_audience",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "request", "title": "Send review or reputation request", "success_metric": "request_delivered", "evidence_hint": "delivery_receipt", "recommended_action_types": ("request_review",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "verify", "title": "Verify public review outcome", "success_metric": "review_publication_verified", "evidence_hint": "review_publication", "recommended_action_types": ("verify_publication",), "estimated_steps": 1, "priority_weight": policy.verification_priority_weight, "checkpoint_required": True},
            )
        if goal_family == "demand_generation":
            return (
                {"phase": "position", "title": "Prepare or improve the offer surface", "success_metric": "offer_surface_live", "evidence_hint": "page_publication", "recommended_action_types": ("publish_service_page",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "activate", "title": "Activate a demand channel", "success_metric": "traffic_or_inquiry_signal", "evidence_hint": "channel_signal", "recommended_action_types": ("launch_campaign", "route_listing"), "estimated_steps": 2, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
                {"phase": "capture", "title": "Capture and verify inbound demand", "success_metric": "qualified_lead_verified", "evidence_hint": "lead_capture", "recommended_action_types": ("capture_leads", "verify_lead"), "estimated_steps": 1, "priority_weight": policy.activation_priority_weight, "checkpoint_required": True},
            )
        return (
            {"phase": "assess", "title": "Assess the current state", "success_metric": "state_assessed", "evidence_hint": "baseline_state", "recommended_action_types": ("assess_state",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
            {"phase": "act", "title": "Run the next best verified action path", "success_metric": "action_executed", "evidence_hint": "execution_receipt", "recommended_action_types": ("select_next_action",), "estimated_steps": 1, "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight, "checkpoint_required": True},
            {"phase": "verify", "title": "Verify the business outcome", "success_metric": "outcome_verified", "evidence_hint": "verification_receipt", "recommended_action_types": ("verify_outcome",), "estimated_steps": 1, "priority_weight": policy.verification_priority_weight, "checkpoint_required": True},
        )

    def _normalize_explicit_steps(self, *, explicit_steps: object, fallback: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        if not isinstance(explicit_steps, (list, tuple)):
            return fallback
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(explicit_steps, start=1):
            if isinstance(item, Mapping):
                row = dict(item)
                title = _text(row.get("title") or row.get("step") or row.get("action_type"))
                if not title:
                    continue
                actions_raw = row.get("recommended_action_types") or row.get("actions") or (row.get("action_type"),)
                if isinstance(actions_raw, (str, bytes)):
                    actions = (_text(actions_raw),) if _text(actions_raw) else ()
                else:
                    actions = tuple(str(x) for x in (actions_raw or ()) if _text(x))
                rows.append({
                    "phase": _text(row.get("phase") or f"step_{index}") or f"step_{index}",
                    "title": title,
                    "success_metric": _text(row.get("success_metric") or row.get("metric") or "step_verified"),
                    "evidence_hint": _text(row.get("evidence_hint") or row.get("evidence") or "execution_receipt"),
                    "recommended_action_types": actions,
                    "estimated_steps": max(1, _safe_int(row.get("estimated_steps"), default=1)),
                    "priority_weight": max(0.1, _safe_float(row.get("priority_weight"), default=1.0)),
                    "checkpoint_required": bool(row.get("checkpoint_required", True)),
                    "parallelizable": bool(row.get("parallelizable", False)),
                    "depends_on": tuple(str(x) for x in (row.get("depends_on") or ()) if _text(x)),
                })
            else:
                title = _text(item)
                if title:
                    rows.append({
                        "phase": f"step_{index}",
                        "title": title,
                        "success_metric": "step_verified",
                        "evidence_hint": "execution_receipt",
                        "recommended_action_types": (_slug(title, fallback=f"step_{index}"),),
                        "estimated_steps": 1,
                        "priority_weight": DEFAULT_GOAL_DECOMPOSITION_POLICY.default_priority_weight,
                        "checkpoint_required": True,
                    })
        return tuple(rows) if rows else fallback

    def decompose(self, *, goal: str, metadata: Mapping[str, Any] | None = None, performance_context: Mapping[str, Any] | None = None, strategy_memory: Mapping[str, Any] | None = None) -> GoalDecompositionResult:
        payload = _safe_dict(metadata)
        perf = _safe_dict(performance_context)
        memory = _safe_dict(strategy_memory)

        goal_family = self.detect_goal_family(goal=goal, metadata=payload)
        planning_horizon = _normalize_horizon(
            payload.get("planning_horizon") or perf.get("preferred_planning_horizon") or memory.get("preferred_horizon") or "week"
        )

        template = self._normalize_explicit_steps(
            explicit_steps=payload.get("long_horizon_steps") or payload.get("steps"),
            fallback=self._default_template(goal_family=goal_family),
        )

        decomposition_patterns = _safe_dict(memory.get("decomposition_patterns"))
        weak_verification = _safe_float(perf.get("verification_rate"), default=1.0) < 0.45
        checkpoint_pressure = _text(_safe_dict(perf.get("long_horizon_signals")).get("checkpoint_readiness"))

        risk_flags: list[str] = []
        if weak_verification:
            risk_flags.append("weak_verification")
        if checkpoint_pressure in {"replan_now", "verify_before_scale", "stabilize_route"}:
            risk_flags.append(checkpoint_pressure)
        for item in memory.get("risk_flags") or ():
            token = _text(item)
            if token and token not in risk_flags:
                risk_flags.append(token)

        tasks: list[GoalDecompositionTask] = []
        previous_task_id: str | None = None
        for index, row in enumerate(template, start=1):
            phase = _text(row.get("phase") or f"step_{index}") or f"step_{index}"
            task_id = f"{_slug(goal_family, fallback='goal')}__{index:02d}__{_slug(phase, fallback='phase')}"
            phase_stats = _safe_dict(decomposition_patterns.get(phase))
            depends_on = tuple(str(x) for x in (row.get("depends_on") or (() if previous_task_id is None else (previous_task_id,))) if _text(x))
            actions_raw = row.get("recommended_action_types") or ()
            if isinstance(actions_raw, (str, bytes)):
                recommended_action_types = (_text(actions_raw),) if _text(actions_raw) else ()
            else:
                recommended_action_types = tuple(str(x) for x in (actions_raw or ()) if _text(x))
            estimated_steps = max(1, _safe_int(row.get("estimated_steps"), default=max(1, _safe_int(phase_stats.get("typical_step_count"), default=1))))
            tasks.append(GoalDecompositionTask(
                task_id=task_id,
                title=_text(row.get("title") or phase),
                phase=phase,
                depends_on=depends_on,
                success_metric=_text(row.get("success_metric") or "step_verified"),
                evidence_hint=_text(row.get("evidence_hint") or "execution_receipt"),
                recommended_action_types=recommended_action_types,
                estimated_steps=estimated_steps,
                priority_weight=max(0.1, _safe_float(row.get("priority_weight"), default=1.0)),
                checkpoint_required=bool(row.get("checkpoint_required", True)),
                parallelizable=bool(row.get("parallelizable", False)) and not weak_verification,
                metadata={
                    "historical_success_rate": max(0.0, min(1.0, _safe_float(phase_stats.get("avg_completion_ratio"), default=0.0))),
                    "historical_verification_rate": max(0.0, min(1.0, _safe_float(phase_stats.get("verified_runs"), default=0.0) / max(1.0, _safe_float(phase_stats.get("observed_runs"), default=1.0)))),
                    "evidence_only": True,
                    "must_not_issue_decision": True,
                },
            ))
            previous_task_id = task_id

        total_estimated_steps = sum(task.estimated_steps for task in tasks)
        checkpoint_every_steps = 1 if total_estimated_steps <= 3 or weak_verification else 2
        decomposition_reason = "explicit_template" if payload.get("long_horizon_steps") or payload.get("steps") else "goal_family_template"
        return GoalDecompositionResult(
            goal_family=goal_family,
            planning_horizon=planning_horizon,
            decomposition_reason=decomposition_reason,
            decomposition_version="v1",
            decomposition_id=f"{_slug(goal_family, fallback='goal')}__{_slug(planning_horizon, fallback='week')}__{len(tasks)}",
            total_estimated_steps=total_estimated_steps,
            checkpoint_every_steps=checkpoint_every_steps,
            tasks=tuple(tasks),
            success_metrics=tuple(task.success_metric for task in tasks if task.success_metric),
            risk_flags=tuple(dict.fromkeys(risk_flags)),
        )


__all__ = [
    "CANON_GOAL_DECOMPOSITION_ENGINE",
    "GOAL_DECOMPOSITION_SCHEMA_VERSION",
    "GoalDecompositionEngine",
    "GoalDecompositionResult",
    "GoalDecompositionTask",
]
