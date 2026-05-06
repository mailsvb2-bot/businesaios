from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.world_state_contract import WorldStateContract
from application.world_state.history_metrics import scalarized_reward_delta, top_expected_value_delta
from application.world_state.history_sample import HistorySample
from application.world_state.history_summary import HistorySummary
from application.world_state.history_window import HistoryWindow


@dataclass
class WorldStateHistoryService:
    window: HistoryWindow

    def record(self, world_state: WorldStateContract) -> HistorySummary:
        self.window.append(HistorySample(created_at_ms=world_state.generated_at_ms, world_state=world_state))
        samples = self.window.all()
        return HistorySummary(
            sample_count=len(samples),
            scalarized_reward_delta=scalarized_reward_delta(samples),
            top_expected_value_delta=top_expected_value_delta(samples),
        )
