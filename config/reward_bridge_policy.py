from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardBridgePolicy:
    primary_weight: float
    secondary_weight: float
    tertiary_weight: float
    min_score: float = -1.0
    max_score: float = 1.0


DEFAULT_FUTURE_VALUE_POLICY = RewardBridgePolicy(
    primary_weight=0.45,
    secondary_weight=0.30,
    tertiary_weight=0.25,
)

DEFAULT_IMMEDIATE_REWARD_POLICY = RewardBridgePolicy(
    primary_weight=0.45,
    secondary_weight=0.35,
    tertiary_weight=0.20,
)
