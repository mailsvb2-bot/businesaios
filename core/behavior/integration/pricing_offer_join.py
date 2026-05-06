from __future__ import annotations

from core.behavior.integration.pricing_band_guard import constrain_price_band


def apply_behavior_to_offer_price_candidate(
    candidate: dict[str, object],
    price_constraints: dict[str, object],
) -> dict[str, object]:
    result = dict(candidate)
    result["band"] = constrain_price_band(
        str(candidate.get("band", "standard")),
        str(price_constraints.get("max_band", "standard")),
    )
    result["pricing_mode"] = str(price_constraints.get("mode", candidate.get("pricing_mode", "normal")))
    if not bool(price_constraints.get("premium_allowed", True)) and result["band"] == "premium":
        result["band"] = "standard"
    return result
