from __future__ import annotations

from contracts.decisioning.world_state_contract import WorldStateContract


def extract_world_state_features(world_state: WorldStateContract) -> dict[str, float]:
    features: dict[str, float] = {}

    for key, value in world_state.user_state.items():
        features[f"user.{key}"] = float(value)
    for key, value in world_state.market_state.items():
        features[f"market.{key}"] = float(value)
    for key, value in world_state.creative_state.items():
        features[f"creative.{key}"] = float(value)
    for key, value in world_state.architecture_state.items():
        features[f"architecture.{key}"] = float(value)
    for key, value in world_state.structure_state.items():
        features[f"structure.{key}"] = float(value)
    for key, value in world_state.flow_state.items():
        features[f"flow.{key}"] = float(value)
    for key, value in world_state.diffusion_state.items():
        features[f"diffusion.{key}"] = float(value)
    for key, value in world_state.economics_state.items():
        features[f"economics.{key}"] = float(value)
    for key, value in world_state.reward_state.items():
        features[f"reward.{key}"] = float(value)

    return features
