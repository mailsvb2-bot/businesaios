from __future__ import annotations

from typing import Mapping

from application.world_state.boundary_rules import assert_world_state_boundary
from application.world_state.creative_state_builder import build_creative_state
from application.world_state.economics_state_builder import build_economics_state
from application.world_state.generic_state_builders import (
    build_architecture_state,
    build_diffusion_state,
    build_flow_state,
    build_structure_state,
)
from application.world_state.history_summary import HistorySummary
from application.world_state.market_state_builder import build_market_state
from application.world_state.reward_state_builder import build_reward_state
from application.world_state.state_id import build_state_id
from application.world_state.user_state_builder import build_user_state
from contracts.decisioning.reward_signal_contract import RewardSignalContract
from contracts.decisioning.world_state_contract import WorldStateContract
from core.creative_intelligence.models import CreativeIntelligenceSnapshot
from runtime.market.market_snapshot import MarketSnapshot


def assemble_world_state(
    *,
    generated_at_ms: int,
    user_observables: Mapping[str, object],
    market_snapshot: MarketSnapshot,
    creative_snapshots: tuple[CreativeIntelligenceSnapshot, ...],
    architecture_state: Mapping[str, float],
    structure_state: Mapping[str, float],
    flow_state: Mapping[str, float],
    diffusion_state: Mapping[str, float],
    reward_signal: RewardSignalContract,
    history_summary: HistorySummary | None = None,
    advisory_flags: dict[str, str] | None = None,
    notes: tuple[str, ...] = (),
) -> WorldStateContract:
    assert_world_state_boundary(dict(advisory_flags or {}))
    state_id = build_state_id(
        generated_at_ms=generated_at_ms,
        salt=str(generated_at_ms),
    )
    return WorldStateContract(
        state_id=state_id,
        generated_at_ms=generated_at_ms,
        user_state=build_user_state(user_observables),
        market_state=build_market_state(market_snapshot),
        creative_state=build_creative_state(creative_snapshots),
        architecture_state=build_architecture_state(architecture_state),
        structure_state=build_structure_state(structure_state),
        flow_state=build_flow_state(flow_state),
        diffusion_state=build_diffusion_state(diffusion_state),
        economics_state=build_economics_state(creative_snapshots),
        reward_state={
            **build_reward_state(reward_signal),
            **({} if history_summary is None else history_summary.as_dict()),
        },
        advisory_flags=dict(advisory_flags or {}),
        notes=tuple(notes),
    )
