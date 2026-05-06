"""Retention feature space.

This module defines the **canonical 200-feature vector** used by the Retention-SaaS layer.

Contract:
- Exactly 200 feature keys.
- Missing features are allowed at extraction time, but the stored vector must be complete
  (defaults filled) to keep the math deterministic.

We intentionally store features as JSON (vector), not as 200 SQL columns:
- avoids schema churn,
- keeps experimentation cheap,
- preserves determinism via an explicit registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from core.retention.feature_registry_audio import KEYS as AUDIO_KEYS
from core.retention.feature_registry_clicks import KEYS as CLICKS_KEYS
from core.retention.feature_registry_monetization import KEYS as MONETIZATION_KEYS
from core.retention.feature_registry_mood import KEYS as MOOD_KEYS
from core.retention.feature_registry_sessions import KEYS as SESSIONS_KEYS
from core.retention.feature_registry_tech import KEYS as TECH_KEYS


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    default: float = 0.0


FEATURE_KEYS: List[str] = (
    SESSIONS_KEYS
    + CLICKS_KEYS
    + AUDIO_KEYS
    + MOOD_KEYS
    + MONETIZATION_KEYS
    + TECH_KEYS
)

assert len(FEATURE_KEYS) == 200
assert len(set(FEATURE_KEYS)) == 200


FEATURES: List[FeatureSpec] = [FeatureSpec(k, 0.0) for k in FEATURE_KEYS]


def default_vector() -> Dict[str, float]:
    return {k: 0.0 for k in FEATURE_KEYS}


def ensure_complete(vec: Dict[str, float]) -> Dict[str, float]:
    """Fill missing keys with defaults (deterministic)."""
    out = default_vector()
    for k, v in (vec or {}).items():
        if k in out:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                continue
    return out
