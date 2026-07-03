from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class WorldModelCompletenessPolicy:
    min_score: float = 0.75
    error_prefix: str = "world" "_model completeness below threshold"


DEFAULT_WORLD_MODEL_COMPLETENESS_POLICY = WorldModelCompletenessPolicy()
