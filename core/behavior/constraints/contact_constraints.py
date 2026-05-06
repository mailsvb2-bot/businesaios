from __future__ import annotations

from core.behavior.contracts.constraints import ContactConstraints


def derive_contact_constraints(observables: dict[str, float]) -> ContactConstraints:
    fatigue = observables.get("fatigue_score", 0.0)
    anti = observables.get("anti_field_level", 0.0)
    cooldown = 2 if anti >= 0.6 else 1 if fatigue >= 0.5 else 0
    cap = 1 if anti >= 0.6 else 2 if fatigue >= 0.5 else 3
    return ContactConstraints(
        retry_cooldown_level=cooldown,
        contact_frequency_cap=cap,
    )
