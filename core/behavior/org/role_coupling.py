from __future__ import annotations

from core.behavior.contracts.person_field import PersonField
from core.behavior.math.vector_ops import clamp, mean
from core.behavior.org.role_weights import role_weight


def compute_role_coupling(role_fields: dict[str, PersonField]) -> dict[str, float]:
    if not role_fields:
        return {
            "weighted_readiness": 0.0,
            "weighted_trust": 0.0,
            "weighted_anti": 0.0,
            "coupling_balance": 0.0,
        }
    weighted_readiness = []
    weighted_trust = []
    weighted_anti = []
    for role, field in role_fields.items():
        weight = role_weight(role)
        weighted_readiness.append(field.dynamic_observables.get("payment_readiness_level", 0.0) * weight)
        weighted_trust.append(field.dynamic_observables.get("trust_level", 0.0) * weight)
        weighted_anti.append(field.dynamic_observables.get("anti_field_level", 0.0) * weight)
    readiness_mean = mean(weighted_readiness)
    trust_mean = mean(weighted_trust)
    anti_mean = mean(weighted_anti)
    balance = clamp((trust_mean + readiness_mean + (1.0 - anti_mean)) / 3.0)
    return {
        "weighted_readiness": clamp(readiness_mean),
        "weighted_trust": clamp(trust_mean),
        "weighted_anti": clamp(anti_mean),
        "coupling_balance": balance,
    }
