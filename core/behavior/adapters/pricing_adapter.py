from __future__ import annotations


def apply_price_constraints(price_constraints: dict[str, object], pricing_state: dict[str, object]) -> dict[str, object]:
    result = dict(pricing_state)
    result["max_band"] = price_constraints.get("max_band", result.get("max_band", "standard"))
    result["mode"] = price_constraints.get("mode", result.get("mode", "normal"))
    result["premium_allowed"] = bool(price_constraints.get("premium_allowed", True))
    return result
