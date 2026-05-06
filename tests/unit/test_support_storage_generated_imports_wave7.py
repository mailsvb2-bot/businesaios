from __future__ import annotations

from runtime.platform.support.storage.artifacts.checkpoint_store import CheckpointStore
from runtime.platform.support.storage.datasets.rollout_store import RolloutStore
from runtime.platform.support.storage.registry.policy_registry_store import PolicyRegistryStore


def test_generated_store_imports_remain_compatible() -> None:
    checkpoint = CheckpointStore()
    rollout = RolloutStore()
    registry = PolicyRegistryStore()

    checkpoint.put("a", 1)
    rollout.put("b", 2)
    registry.put("c", 3)

    assert checkpoint.get("a") == 1
    assert rollout.get("b") == 2
    assert registry.get("c") == 3
