from __future__ import annotations

"""Off-policy evaluation (OPE) primitives for pricing.

We assume logged events include:
  pricing_action_logged@v1 payload:
    {
      "offer_arm": "...",
      "price_rub": 1234,
      "propensity": "logged_propensity",
      "reward_minor": 10000,
      "policy_id": "pricing_rl_v1"
    }

This module is pure and supports simple IPS estimate for a target policy that
replays a deterministic action (price point).
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable

from config.pricing_retention_policy import (
    DEFAULT_PRICING_OFF_POLICY_DEFAULTS,
    PricingOffPolicyDefaults,
)


@dataclass(frozen=True)
class IPSEstimate:
    n: int
    estimate_reward_minor: float
    effective_n: float
    note: str = ""


def ips_estimate_for_price(
    event_store: Any,
    *,
    tenant_id: str,
    offer_arm: str,
    target_price_rub: int,
    start_ms: int,
    end_ms: int | None = None,
    event_type: str = "pricing_action_logged@v1",
    max_events: int = 5000,
    policy: PricingOffPolicyDefaults = DEFAULT_PRICING_OFF_POLICY_DEFAULTS,
) -> IPSEstimate:
    """IPS estimate E[reward] for target policy that always picks target_price_rub."""
    events = _iter_events(
        event_store,
        tenant_id=tenant_id,
        event_type=event_type,
        start_ms=start_ms,
        end_ms=end_ms,
        limit=max_events,
    )
    wsum = float(policy.zero_effective_n)
    rsum = float(policy.zero_reward_minor)
    n = 0
    for e in events:
        payload = e.get("payload") if isinstance(e, dict) else None
        if not isinstance(payload, dict):
            continue
        if str(payload.get("offer_arm") or "") != str(offer_arm):
            continue
        try:
            price = int(payload.get("price_rub") or 0)
        except Exception:
            continue
        if int(price) != int(target_price_rub):
            continue
        try:
            prop = float(payload.get("propensity") or policy.zero_propensity)
        except Exception:
            prop = float(policy.zero_propensity)
        if prop <= float(policy.zero_propensity):
            continue
        try:
            reward = float(payload.get("reward_minor") or policy.zero_reward_minor)
        except Exception:
            reward = float(policy.zero_reward_minor)
        w = float(policy.inverse_propensity_numerator) / prop
        wsum += w
        rsum += w * reward
        n += 1
    if n == 0 or wsum <= float(policy.zero_effective_n):
        return IPSEstimate(
            n=0,
            estimate_reward_minor=float(policy.zero_reward_minor),
            effective_n=float(policy.zero_effective_n),
            note="no_data",
        )
    return IPSEstimate(
        n=int(n),
        estimate_reward_minor=float(rsum / wsum),
        effective_n=float(wsum),
    )


def _iter_events(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int,
    end_ms: int | None,
    limit: int,
) -> Iterable[dict[str, Any]]:
    it = getattr(event_store, "iter_events", None)
    if callable(it):
        yield from it(
            tenant_id=tenant_id,
            event_types=(event_type,),
            start_ms=int(start_ms),
            end_ms=end_ms,
            limit=int(limit),
        )
        return
    latest = getattr(event_store, "latest_events", None)
    if callable(latest):
        yield from latest(tenant_id=tenant_id, event_types=(event_type,), limit=int(limit)) or []
