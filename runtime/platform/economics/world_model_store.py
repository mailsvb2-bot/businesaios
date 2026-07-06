"""Backward-compatible public facade for governed world-model stores.

Contracts live in world_model_store_contracts.
Construction lives in world_model_store_factory.
This facade intentionally owns no implementation logic.
"""

from __future__ import annotations

from runtime.platform.economics.world_model_store_contracts import (
    FileWorldModelStore,
    WorldModelStorePort,
)
from runtime.platform.economics.world_model_store_factory import build_world_model_store

CANON_WORLD_MODEL_STORE_FACADE = True

__all__ = [
    "CANON_WORLD_MODEL_STORE_FACADE",
    "FileWorldModelStore",
    "WorldModelStorePort",
    "build_world_model_store",
]
