from __future__ import annotations

"""Safe rollout helper for RL pricing.

Principle:
  - Default OFF.
  - Gradual enable by tenant via feature flags.
  - Optional percent rollout by stable hashing of (tenant, user, offer_arm).

This module is pure.
"""

import hashlib
from dataclasses import dataclass

from core.flags.provider import FeatureFlagProvider, FlagContext


@dataclass(frozen=True)
class RolloutDecision:
    enabled: bool
    reason: str


def is_rl_pricing_enabled(
    *,
    flags: FeatureFlagProvider,
    tenant_id: str,
    user_id: str | None,
    offer_arm: str,
    rollout_pct: int = 0,
) -> RolloutDecision:
    # Hard flag gate
    if not flags.enabled("RL_PRICING", ctx=FlagContext(tenant_id=tenant_id, user_id=user_id)):
        return RolloutDecision(False, "flag_off")

    pct = max(0, min(100, int(rollout_pct)))
    if pct <= 0:
        return RolloutDecision(True, "flag_on")

    key = f"{tenant_id}|{user_id or ''}|{offer_arm}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) % 100
    return RolloutDecision(bucket < pct, f"rollout_{pct}%")
