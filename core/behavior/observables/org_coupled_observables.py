from __future__ import annotations

from core.behavior.contracts.person_field import PersonField
from core.behavior.math.vector_ops import clamp
from core.behavior.org.role_coupling import compute_role_coupling


def compute_coupled_org_observables(role_fields: dict[str, PersonField]) -> dict[str, float]:
    coupling = compute_role_coupling(role_fields)
    return {
        "org_weighted_readiness": coupling["weighted_readiness"],
        "org_weighted_trust": coupling["weighted_trust"],
        "org_weighted_anti": coupling["weighted_anti"],
        "org_coupling_balance": coupling["coupling_balance"],
        "org_blocker_pressure": clamp(coupling["weighted_anti"] * (1.0 - coupling["weighted_trust"])),
    }
