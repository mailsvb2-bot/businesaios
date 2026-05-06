from __future__ import annotations

from contracts.decisioning.world_state_contract import WorldStateContract


def build_metadata(world_state: WorldStateContract) -> dict[str, str]:
    return {
        "state_id": world_state.state_id,
        "generated_at_ms": str(world_state.generated_at_ms),
        "packet_name": str(world_state.advisory_flags.get("packet_name", "")),
    }
