"""Product capability gate (Engine-level).

This is NOT a second brain.
It is a deterministic safety layer that prevents a product from executing
actions that its ProductContext.modules did not enable.

We gate at RuntimeExecutor time (after Decision issuance) because:
  - DecisionCore stays universal
  - product configs are inputs into state
  - enforcement happens right before irreversible side-effects

The gate is intentionally small and explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

@dataclass(frozen=True)
class ProductGateVerdict:
    allow: bool
    reason: str = ""


def _mod_enabled(mods: Mapping[str, Any] | None, key: str) -> bool:
    if not mods:
        return False
    try:
        return bool(mods.get(key))
    except Exception:
        return False


def review_action(*, product: Mapping[str, Any] | None, action: str) -> ProductGateVerdict:
    """Return allow/deny for action under product.modules.

    Unknown actions are not denied here — they are denied earlier by schema
    registry / constitution. This gate only enforces *capabilities*.
    """

    p = dict(product or {})
    mods = p.get("modules") if isinstance(p.get("modules"), dict) else {}
    a = str(action or "").strip()

    # Map actions -> required module flags
    requirements = {
        "send_audio@v1": "audio",
        "change_price@v1": "pricing",
        "offer_product@v1": "offers",
        "send_offer@v1": "offers",
        "send_reminder@v1": "reminders",
    }

    req = requirements.get(a)
    if not req:
        return ProductGateVerdict(True, "")

    if _mod_enabled(mods, req):
        return ProductGateVerdict(True, "")

    domain = str(p.get("domain") or "")
    pid = str(p.get("product_id") or "")
    return ProductGateVerdict(False, f"CAPABILITY_DISABLED:{req}:action={a}:domain={domain}:product_id={pid}")
