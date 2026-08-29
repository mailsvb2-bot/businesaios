from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.decision_context_projection import DecisionContextProjection


@dataclass(frozen=True)
class HistorySample:
    created_at_ms: int
    world_state: DecisionContextProjection
