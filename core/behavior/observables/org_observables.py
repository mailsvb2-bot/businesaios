from __future__ import annotations

from core.behavior.contracts.person_field import PersonField
from core.behavior.math.vector_ops import clamp, mean


def compute_org_observables(role_fields: dict[str, PersonField]) -> dict[str, float]:
    if not role_fields:
        return {
            "org_alignment_score": 0.0,
            "org_purchase_probability": 0.0,
            "org_blocker_index": 0.0,
            "org_finance_resistance": 0.0,
            "org_decision_sync_score": 0.0,
            "org_champion_strength": 0.0,
            "org_internal_conflict_score": 0.0,
        }
    readiness = [field.dynamic_observables.get("payment_readiness_level", 0.0) for field in role_fields.values()]
    trusts = [field.dynamic_observables.get("trust_level", 0.0) for field in role_fields.values()]
    anti = [field.dynamic_observables.get("anti_field_level", 0.0) for field in role_fields.values()]
    coherence = [field.dynamic_observables.get("coherence_score", 0.0) for field in role_fields.values()]
    alignment = clamp((mean(readiness) + mean(trusts) + mean(coherence)) / 3.0)
    blocker = clamp(max(anti) if anti else 0.0)
    finance_resistance = role_fields.get("finance", role_fields.get("decision_maker", next(iter(role_fields.values())))).dynamic_observables.get("anti_field_level", 0.0)
    champion_strength = role_fields.get("champion", next(iter(role_fields.values()))).dynamic_observables.get("trust_level", 0.0)
    return {
        "org_alignment_score": alignment,
        "org_purchase_probability": clamp((alignment + (1.0 - blocker)) / 2.0),
        "org_blocker_index": blocker,
        "org_finance_resistance": clamp(finance_resistance),
        "org_decision_sync_score": clamp(mean(coherence)),
        "org_champion_strength": clamp(champion_strength),
        "org_internal_conflict_score": clamp(1.0 - alignment),
    }
