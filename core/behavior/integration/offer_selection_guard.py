from __future__ import annotations


def filter_candidates_by_behavior_constraints(
    candidates: list[dict[str, object]],
    offer_constraints: dict[str, object],
) -> list[dict[str, object]]:
    disallow_prefixes = tuple(str(v) for v in offer_constraints.get("disallow_offer_prefixes", tuple()))
    aggressive_allowed = bool(offer_constraints.get("aggressive_allowed", True))
    paywall_first_allowed = bool(offer_constraints.get("paywall_first_allowed", True))

    filtered: list[dict[str, object]] = []
    for candidate in candidates:
        offer_id = str(candidate.get("offer_id", ""))
        placement = str(candidate.get("placement", ""))
        is_aggressive = bool(candidate.get("aggressive", False))
        if disallow_prefixes and offer_id.startswith(disallow_prefixes):
            continue
        if not aggressive_allowed and is_aggressive:
            continue
        if not paywall_first_allowed and placement == "paywall_first":
            continue
        filtered.append(candidate)
    return filtered
