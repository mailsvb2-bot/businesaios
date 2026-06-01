from __future__ import annotations

"""Canonical runtime public surface for world-state types."""

from application.world_state.history_service import WorldStateHistoryService
from application.world_state.history_summary import HistorySummary
from application.world_state.recommendation_packet_builder import build_recommendation_packet
from application.world_state.world_state_assembler import assemble_world_state
from core.reward_bridge.reward_signal_builder import build_reward_signal
from kernel.world_state import WorldStateV1
from runtime.world_state.contract import (
    CANONICAL_WORLD_STATE_IMPORT_PATH,
    RUNTIME_WORLD_STATE_PUBLIC_API,
    WORLD_STATE_CANON,
)

__all__ = [
    'CANON_RUNTIME_WORLD_STATE_NAMESPACE',
    "HistorySummary",
    "WorldStateHistoryService",
    "assemble_world_state",
    "build_recommendation_packet",
    "build_reward_signal",
    "CANONICAL_WORLD_STATE_IMPORT_PATH",
    "RUNTIME_WORLD_STATE_PUBLIC_API",
    "WORLD_STATE_CANON",
    "WorldStateV1",
]

CANON_RUNTIME_WORLD_STATE_NAMESPACE = True


