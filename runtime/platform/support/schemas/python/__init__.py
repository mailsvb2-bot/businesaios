"""Canonical physical schema entrypoints backed by schema_catalog."""

from __future__ import annotations


from typing import Any

from runtime.platform.support.schemas.schema_catalog import schema_for

CANON_RUNTIME_SUPPORT_SCHEMA_PYTHON_PACKAGE_OWNER = True
CANON_COMPAT_SHIM = True

def checkpoint_schema() -> dict[str, Any]:
    return schema_for("checkpoint")

def episode_schema() -> dict[str, Any]:
    return schema_for("episode")

def evaluation_schema() -> dict[str, Any]:
    return schema_for("evaluation")

def experiment_schema() -> dict[str, Any]:
    return schema_for("experiment")

def incident_schema() -> dict[str, Any]:
    return schema_for("incident")

def policy_schema() -> dict[str, Any]:
    return schema_for("policy")

def reward_schema() -> dict[str, Any]:
    return schema_for("reward")

def rollout_schema() -> dict[str, Any]:
    return schema_for("rollout")

def trajectory_schema() -> dict[str, Any]:
    return schema_for("trajectory")

def transition_schema() -> dict[str, Any]:
    return schema_for("transition")

__all__ = [
    "checkpoint_schema",
    "episode_schema",
    "evaluation_schema",
    "experiment_schema",
    "incident_schema",
    "policy_schema",
    "reward_schema",
    "rollout_schema",
    "trajectory_schema",
    "transition_schema",
]
