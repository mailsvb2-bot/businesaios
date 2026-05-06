from __future__ import annotations

"""Canonical validator surface backed by schema_catalog with compat alias submodules."""

from typing import Any

from runtime.platform.support.schemas.schema_catalog import is_valid_payload

def valid_checkpoint(payload: dict[str, Any]) -> bool:
    return is_valid_payload("checkpoint", payload)

def valid_episode(payload: dict[str, Any]) -> bool:
    return is_valid_payload("episode", payload)

def valid_evaluation(payload: dict[str, Any]) -> bool:
    return is_valid_payload("evaluation", payload)

def valid_experiment(payload: dict[str, Any]) -> bool:
    return is_valid_payload("experiment", payload)

def valid_reward(payload: dict[str, Any]) -> bool:
    return is_valid_payload("reward", payload)

def valid_rollout(payload: dict[str, Any]) -> bool:
    return is_valid_payload("rollout", payload)

def valid_trajectory(payload: dict[str, Any]) -> bool:
    return is_valid_payload("trajectory", payload)

_ALIAS_EXPORTS = {
    "checkpoint_validator": "valid_checkpoint",
    "episode_validator": "valid_episode",
    "evaluation_validator": "valid_evaluation",
    "experiment_validator": "valid_experiment",
    "reward_validator": "valid_reward",
    "rollout_validator": "valid_rollout",
    "trajectory_validator": "valid_trajectory",
}

__all__ = [
    "valid_checkpoint",
    "valid_episode",
    "valid_evaluation",
    "valid_experiment",
    "valid_reward",
    "valid_rollout",
    "valid_trajectory",
] + list(_ALIAS_EXPORTS)
