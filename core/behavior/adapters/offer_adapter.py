from __future__ import annotations


def filter_offer_candidates(candidates: list[str], offer_constraints: dict[str, object]) -> list[str]:
    prefixes = tuple(offer_constraints.get("disallow_offer_prefixes", tuple()))
    aggressive_allowed = bool(offer_constraints.get("aggressive_allowed", True))
    filtered: list[str] = []
    for candidate in candidates:
        if prefixes and candidate.startswith(prefixes):
            continue
        if not aggressive_allowed and candidate.startswith("offer_aggressive"):
            continue
        filtered.append(candidate)
    return filtered
