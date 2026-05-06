"""Causal inference primitives.

Goal:
- Provide small, composable building blocks for estimating causal effects from
  observational data and simple experiments.

Design principles:
- No "god objects": small modules with explicit inputs/outputs.
- Pure core (no network/provider imports).
- Deterministic-by-default; randomness must be explicitly seeded.

Public API lives in :mod:`core.causal.api`.
"""

from core.causal.api import (
    CausalQuery,
    CausalResult,
    EffectEstimate,
    estimate_causal_effect,
)

__all__ = [
    "CausalQuery",
    "CausalResult",
    "EffectEstimate",
    "estimate_causal_effect",
]
