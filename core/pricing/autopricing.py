from __future__ import annotations

"""Autopricing suggestions (read-only).

This module is intentionally *pure*:
- It does not write events.
- It does not call network.
- It derives suggestions from the canonical event stream.

Use-cases:
- Telegram UI can display suggested prices for tariffs.
- Admin read models can surface recommendations.

The underlying picker is event-sourced RL pricing (Thompson sampling) and is
safe-by-construction when used in read-only mode.
"""

from dataclasses import dataclass
from typing import Any, Optional
from collections.abc import Iterable

from core.pricing.rl_picker import RLPricingConfig, choose_price_rub
from core.pricing.stop_loss import StopLossConfig, should_apply_price


@dataclass(frozen=True)
class AutopricingConfig:
    enabled: bool = False
    rl: RLPricingConfig = RLPricingConfig(enabled=True)
    stop_loss: StopLossConfig = StopLossConfig(enabled=False)


def suggest_prices_for_plans(
    event_store: Any,
    *,
    tenant_id: str,
    plans: Iterable[dict[str, Any]],
    config: AutopricingConfig,
    context_key: str = "",
) -> dict[str, int]:
    """Return {plan_id: suggested_price_rub} for active plans.

    - plan['price'] is treated as base price.
    - offer_arm uses plan['plan_code'] (stable).
    - context_key may represent a segment/traffic_source.
    """
    if not config.enabled:
        return {}

    out: dict[str, int] = {}
    for p in list(plans):
        if not isinstance(p, dict):
            continue
        try:
            pid = int(p.get("plan_id") or 0)
            base = int(p.get("price") or 0)
            arm = str(p.get("plan_code") or p.get("code") or "").strip()
            if pid <= 0 or base <= 0 or not arm:
                continue

            pick = choose_price_rub(
                event_store,
                tenant_id=str(tenant_id),
                offer_arm=str(arm),
                base_price_rub=int(base),
                config=config.rl,
                context_key=str(context_key or "").strip(),
            )
            suggested = int(pick.price_rub)

            if config.stop_loss.enabled:
                gate = should_apply_price(
                    event_store,
                    tenant_id=str(tenant_id),
                    offer_arm=str(arm),
                    candidate_price_rub=int(suggested),
                    base_price_rub=int(base),
                    context_key=str(context_key or "").strip(),
                    config=config.stop_loss,
                )
                if not gate.allow:
                    suggested = int(base)

            out[str(pid)] = int(suggested)
        except Exception:
            continue
    return out
