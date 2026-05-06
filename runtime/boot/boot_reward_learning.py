from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Reward/learning assembly helpers extracted from boot_core_assembly."""

from typing import Any

from runtime.boot.core_assembly_parts import build_reward_and_learning_components


def build_reward_learning(*, snapshot_store: Any, event_log: Any, model_registry: Any = None):
    return build_reward_and_learning_components(
        snapshot_store=snapshot_store,
        event_log=event_log,
        model_registry=model_registry,
    )


__all__ = ["CANON_BOOT_WIRING_ONLY", "build_reward_learning"]
