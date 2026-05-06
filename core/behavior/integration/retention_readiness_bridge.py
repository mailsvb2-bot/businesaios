from __future__ import annotations

from core.behavior.math.vector_ops import clamp


def adjust_readiness_score(base_readiness: float, behavior_observables: dict[str, float]) -> float:
    trust = behavior_observables.get("trust_level", 0.0)
    payment = behavior_observables.get("payment_readiness_level", 0.0)
    resonance = behavior_observables.get("resonance_readiness", 0.0)
    anti = behavior_observables.get("anti_field_level", 0.0)
    score = (base_readiness + trust + payment + resonance) / 4.0
    score *= 1.0 - anti * 0.4
    return clamp(score)
