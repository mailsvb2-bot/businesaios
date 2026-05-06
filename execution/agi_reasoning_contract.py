from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANON_AGI_REASONING_CONTRACT = True
AGI_REASONING_SCHEMA_VERSION = "agi_reasoning@v3"
AGI_REASONING_MODE = "state_enrichment_only"


@dataclass(frozen=True)
class AGIGoalCandidate:
    goal_id: str
    goal: str
    goal_family: str
    priority: str = "medium"
    source: str = "unknown"
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": str(self.goal_id),
            "goal": str(self.goal),
            "goal_family": str(self.goal_family),
            "priority": str(self.priority),
            "source": str(self.source),
            "rationale": str(self.rationale),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AGIReasoningSummary:
    schema_version: str = AGI_REASONING_SCHEMA_VERSION
    reasoning_mode: str = AGI_REASONING_MODE
    selected_goal: dict[str, Any] | None = None
    goal_candidates: tuple[dict[str, Any], ...] = ()
    strategy_hints: tuple[dict[str, Any], ...] = ()
    planning_horizon: str = "week"
    decomposed_focus: tuple[str, ...] = ()
    world_snapshot: dict[str, Any] = field(default_factory=dict)
    opportunity_signals: tuple[dict[str, Any], ...] = ()
    learning_context: dict[str, Any] = field(default_factory=dict)
    explainability: dict[str, Any] = field(default_factory=dict)
    suppressed_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": str(self.schema_version),
            "reasoning_mode": str(self.reasoning_mode),
            "selected_goal": None if self.selected_goal is None else dict(self.selected_goal),
            "goal_candidates": [dict(item) for item in self.goal_candidates],
            "strategy_hints": [dict(item) for item in self.strategy_hints],
            "planning_horizon": str(self.planning_horizon),
            "decomposed_focus": [str(x) for x in self.decomposed_focus],
            "world_snapshot": dict(self.world_snapshot),
            "opportunity_signals": [dict(item) for item in self.opportunity_signals],
            "learning_context": dict(self.learning_context),
            "explainability": dict(self.explainability),
            "suppressed_reasons": [str(x) for x in self.suppressed_reasons],
        }


def compact_goal_for_trace(goal: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(goal or {})
    out = {
        "goal": str(payload.get("goal") or ""),
        "goal_family": str(payload.get("goal_family") or ""),
        "priority": str(payload.get("priority") or ""),
        "source": str(payload.get("source") or ""),
    }
    return {key: value for key, value in out.items() if value}


def compact_strategy_hint_for_trace(hint: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(hint or {})
    out = {
        "hint_key": str(payload.get("hint_key") or ""),
        "confidence": payload.get("confidence"),
        "reason": str(payload.get("reason") or ""),
    }
    return {key: value for key, value in out.items() if value not in ("", None)}


__all__ = [
    "CANON_AGI_REASONING_CONTRACT",
    "AGI_REASONING_SCHEMA_VERSION",
    "AGI_REASONING_MODE",
    "AGIGoalCandidate",
    "AGIReasoningSummary",
    "compact_goal_for_trace",
    "compact_strategy_hint_for_trace",
]
