from __future__ import annotations

from core.behavior.contracts.constraints import PriceConstraints


def derive_price_constraints(observables: dict[str, float], guardrails_violation: bool = False) -> PriceConstraints:
    if guardrails_violation:
        return PriceConstraints(max_band="low", mode="safe", premium_allowed=False)
    anti = observables.get("anti_field_level", 0.0)
    trust = observables.get("trust_level", 0.0)
    readiness = observables.get("payment_readiness_level", 0.0)
    if anti >= 0.6 or trust <= 0.35:
        return PriceConstraints(max_band="low", mode="protect", premium_allowed=False)
    if readiness >= 0.7 and trust >= 0.6:
        return PriceConstraints(max_band="premium", mode="normal", premium_allowed=True)
    return PriceConstraints(max_band="standard", mode="normal", premium_allowed=True)
