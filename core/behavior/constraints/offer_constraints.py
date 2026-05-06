from __future__ import annotations

from core.behavior.contracts.constraints import OfferConstraints


def derive_offer_constraints(observables: dict[str, float], guardrails_violation: bool = False) -> OfferConstraints:
    if guardrails_violation:
        return OfferConstraints(
            aggressive_allowed=False,
            paywall_first_allowed=False,
            disallow_offer_prefixes=("offer_90", "offer_bundle"),
        )
    anti = observables.get("anti_field_level", 0.0)
    resonance = observables.get("resonance_readiness", 0.0)
    aggressive_allowed = anti < 0.45 and resonance >= 0.55
    return OfferConstraints(
        aggressive_allowed=aggressive_allowed,
        paywall_first_allowed=anti < 0.35,
        disallow_offer_prefixes=("offer_90",) if anti >= 0.5 else tuple(),
    )
