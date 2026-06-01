from __future__ import annotations

"""Deterministic constraints derived from behavioral observables."""

from typing import Any, Dict, Mapping


def price_constraints_from_behavior(
    *,
    behavior: Mapping[str, Any],
    product: Mapping[str, Any],
) -> dict[str, Any]:
    b = dict(behavior or {})
    anti = float(b.get("anti") or 0.0)
    trust = float(b.get("trust_index") or 0.0)
    coherence = float(b.get("coherence") or 0.0)
    p_buy = float(b.get("purchase_probability") or 0.0)

    org = b.get("org")
    if isinstance(org, dict) and org:
        blocker = float(org.get("org_blocker_index") or 0.0)
        align = float(org.get("org_alignment") or 0.0)
    else:
        blocker = 0.0
        align = 1.0

    score = 0.0
    score += 0.45 * p_buy
    score += 0.25 * trust
    score += 0.20 * coherence
    score += 0.10 * align
    score -= 0.55 * anti
    score -= 0.35 * blocker

    if anti >= 0.45 or trust <= 0.25 or coherence <= 0.22 or blocker >= 0.45:
        max_band = "low"
    elif score >= 0.62 and anti <= 0.20 and trust >= 0.45 and coherence >= 0.45:
        max_band = "premium"
    else:
        max_band = "standard"

    return {
        "max_band": max_band,
        "score": float(max(-1.0, min(1.0, score))),
        "anti": float(max(0.0, min(1.0, anti))),
        "trust": float(max(0.0, min(1.0, trust))),
        "coherence": float(max(0.0, min(1.0, coherence))),
        "is_b2b": bool(isinstance(org, dict) and bool(org)),
    }


__all__ = ["price_constraints_from_behavior"]
