from __future__ import annotations

def apply_soft_backoff_preset(world_state: dict[str, object]) -> dict[str, object]:
    result = dict(world_state)
    behavior = dict(result.get("behavior", {}))
    if not behavior.get("guardrails_violation"):
        return result

    result.setdefault("price_constraints", {})
    result["price_constraints"] = {
        **dict(result["price_constraints"]),
        "max_band": "low",
        "mode": "safe",
        "premium_allowed": False,
    }
    result.setdefault("offer_constraints", {})
    result["offer_constraints"] = {
        **dict(result["offer_constraints"]),
        "aggressive_allowed": False,
        "paywall_first_allowed": False,
        "disallow_offer_prefixes": ("offer_90", "offer_bundle"),
    }
    return result
