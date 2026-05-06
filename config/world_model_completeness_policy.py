from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class WorldModelCompletenessPolicy:
    min_score: float = 0.75
    error_prefix: str = "world_model completeness below threshold"


DEFAULT_WORLD_MODEL_COMPLETENESS_POLICY = WorldModelCompletenessPolicy()
