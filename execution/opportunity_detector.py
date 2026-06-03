from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from application.memory.business_operating_memory import project_business_memory_state_context

CANON_OPPORTUNITY_DETECTOR = True


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


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


@dataclass(frozen=True, slots=True)
class OpportunitySignal:
    signal_type: str
    priority: str
    title: str
    rationale: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "priority": self.priority,
            "title": self.title,
            "rationale": self.rationale,
            "evidence": dict(self.evidence),
        }


class OpportunityDetector:
    def detect(self, world_state: Mapping[str, Any] | None) -> tuple[OpportunitySignal, ...]:
        state = _safe_dict(world_state)
        meta = _safe_dict(state.get("meta"))
        observations = _safe_dict(state.get("observations"))
        memory = project_business_memory_state_context(_safe_dict(meta.get("business_memory_evidence")))
        closed_loop = _safe_dict(meta.get("execution_closed_loop"))
        signals: list[OpportunitySignal] = []
        inbound_leads = _safe_int(observations.get("inbound_leads"))
        outbound_count = _safe_int(observations.get("outbound_count"))
        conversion_rate = _safe_float(observations.get("conversion_rate"))
        revenue_trend = _safe_float(observations.get("revenue_trend"))
        recurring_failures = _safe_list(memory.get("recurring_failures"))
        active_goals = [str(item) for item in _safe_list(memory.get("active_goals")) if str(item).strip()]
        recent_failed_runs = _safe_int(closed_loop.get("recent_failed_runs"))

        if inbound_leads > 0 and 0.0 < conversion_rate < 0.05:
            signals.append(OpportunitySignal("conversion_gap", "high", "Observed low conversion on existing demand", "Inbound demand exists, but conversion remains low", {"inbound_leads": inbound_leads, "conversion_rate": conversion_rate}))
        if inbound_leads == 0 and outbound_count == 0:
            signals.append(OpportunitySignal("demand_gap", "high", "No active demand motion observed", "Neither inbound nor outbound activity is currently observed", {"inbound_leads": inbound_leads, "outbound_count": outbound_count}))
        if recent_failed_runs >= 3 or recurring_failures:
            signals.append(OpportunitySignal("execution_instability", "high", "Execution instability observed", "Closed-loop history or business memory shows repeated failures", {"recent_failed_runs": recent_failed_runs, "recurring_failures_count": len(recurring_failures)}))
        if revenue_trend < 0:
            signals.append(OpportunitySignal("negative_revenue_trend", "medium", "Negative revenue trend observed", "Observed revenue trend is below zero", {"revenue_trend": revenue_trend}))
        if not active_goals:
            signals.append(OpportunitySignal("goal_gap", "medium", "No active goals registered", "Business memory evidence has no active goals", {"active_goals_count": len(active_goals)}))
        return tuple(signals)


__all__ = ["CANON_OPPORTUNITY_DETECTOR", "OpportunityDetector", "OpportunitySignal"]
