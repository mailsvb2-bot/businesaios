from __future__ import annotations

_BAND_ORDER = {"low": 0, "standard": 1, "premium": 2}


def merge_behavior_price_constraints(world_state: dict[str, object], behavior_payload: dict[str, object]) -> dict[str, object]:
    result = dict(world_state)
    existing = dict(result.get("price_constraints", {}))
    incoming = dict(behavior_payload.get("price_constraints", {}))
    existing_band = str(existing.get("max_band", "premium"))
    incoming_band = str(incoming.get("max_band", existing_band))
    chosen_band = existing_band if _BAND_ORDER.get(existing_band, 2) <= _BAND_ORDER.get(incoming_band, 2) else incoming_band
    result["price_constraints"] = {
        **existing,
        **incoming,
        "max_band": chosen_band,
    }
    return result
