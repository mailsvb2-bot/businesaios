from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.world_state_contract import WorldStateContract


@dataclass(frozen=True)
class HistorySample:
    created_at_ms: int
    world_state: WorldStateContract
