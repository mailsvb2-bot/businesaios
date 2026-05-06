from __future__ import annotations

from core.behavior.constraints.contact_constraints import derive_contact_constraints
from core.behavior.constraints.offer_constraints import derive_offer_constraints
from core.behavior.constraints.price_constraints import derive_price_constraints
from core.behavior.constraints.safety_constraints import derive_safety_constraints


def build_decisioncore_behavior_payload(observables: dict[str, float], policy_denials: int = 0) -> dict[str, object]:
    safety = derive_safety_constraints(observables, policy_denials=policy_denials)
    price = derive_price_constraints(observables, guardrails_violation=safety.guardrails_violation)
    offer = derive_offer_constraints(observables, guardrails_violation=safety.guardrails_violation)
    contact = derive_contact_constraints(observables)
    return {
        "behavior": {
            **observables,
            "guardrails_violation": safety.guardrails_violation,
            "safe_mode_recommended": safety.safe_mode_recommended,
        },
        "price_constraints": {
            "max_band": price.max_band,
            "mode": price.mode,
            "premium_allowed": price.premium_allowed,
        },
        "offer_constraints": {
            "aggressive_allowed": offer.aggressive_allowed,
            "paywall_first_allowed": offer.paywall_first_allowed,
            "disallow_offer_prefixes": offer.disallow_offer_prefixes,
        },
        "contact_constraints": {
            "retry_cooldown_level": contact.retry_cooldown_level,
            "contact_frequency_cap": contact.contact_frequency_cap,
        },
    }
