from __future__ import annotations

_ALLOWED_KEYS = {
    "behavior",
    "price_constraints",
    "offer_constraints",
    "contact_constraints",
}


def assert_behavior_payload_is_non_executable(payload: dict[str, object]) -> None:
    unexpected = set(payload.keys()) - _ALLOWED_KEYS
    if unexpected:
        raise ValueError(f"Behavior layer attempted to emit unsupported keys: {sorted(unexpected)}")
    if "actions" in payload or "selected_offer" in payload or "winner" in payload:
        raise ValueError("Behavior layer cannot emit executable decisions")
