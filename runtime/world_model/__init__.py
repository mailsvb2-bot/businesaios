from __future__ import annotations

"""Canonical runtime public surface for world-model contracts and helpers.

Runtime boot, handlers and integration code should import world-model types and
services from here instead of reaching into core.world_model internals directly.
"""

from application.decision_state.world_model_metadata import (
    extract_pinned_world_model_meta_from_payload,
    extract_world_model_metadata,
)
from application.decision_state.world_model_replay import replay_state_against_world_model
from runtime.public_api_alias import install_public_api_alias
from core.world_model.contracts import WorldSnapshot, WorldSnapshotBuilderPort, WorldSnapshotRequest
from core.world_model.explainers.world_snapshot_explainer import WorldSnapshotExplainer, explain_world_snapshot
from core.world_model.repositories.snapshot_repository import InMemorySnapshotRepository
from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput, WorldModelBuildResult
from runtime.world_model.contract import RUNTIME_WORLD_MODEL_PUBLIC_API, WORLD_MODEL_CANON

CANON_RUNTIME_WORLD_MODEL_PUBLIC_API = True

__all__ = [
    'CANON_RUNTIME_WORLD_MODEL_NAMESPACE', 
    "replay_state_against_world_model",
    "CANON_RUNTIME_WORLD_MODEL_PUBLIC_API",
    "InMemorySnapshotRepository",
    "RUNTIME_WORLD_MODEL_PUBLIC_API",
    "WORLD_MODEL_CANON",
    "WorldModelBuildInput",
    "WorldModelBuildResult",
    "WorldModelService",
    "WorldSnapshot",
    "WorldSnapshotBuilderPort",
    "WorldSnapshotExplainer",
    "WorldSnapshotRequest",
    "extract_pinned_world_model_meta_from_payload",
    "extract_world_model_metadata",
    "explain_world_snapshot",
]

CANON_RUNTIME_WORLD_MODEL_NAMESPACE = True



install_public_api_alias(__name__)
