from __future__ import annotations

from application.world_state.history_service import WorldStateHistoryService
from application.world_state.history_window import HistoryWindow
from contracts.decisioning.world_state_contract import WorldStateContract


def _state(ts: int, scalarized_value: float, ev: float) -> WorldStateContract:
    return WorldStateContract(
        state_id=str(ts),
        generated_at_ms=ts,
        user_state={},
        market_state={},
        creative_state={"top_expected_value_score": ev},
        architecture_state={},
        structure_state={},
        flow_state={},
        diffusion_state={},
        economics_state={},
        reward_state={"scalarized_value": scalarized_value},
        advisory_flags={},
        notes=(),
    )


def test_world_state_history_tracks_delta() -> None:
    service = WorldStateHistoryService(window=HistoryWindow(capacity=5))
    service.record(_state(1, 0.1, 0.2))
    summary = service.record(_state(2, 0.4, 0.5))
    assert summary.scalarized_reward_delta > 0.0
    assert summary.top_expected_value_delta > 0.0
