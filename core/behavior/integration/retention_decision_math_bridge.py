from __future__ import annotations

from core.behavior.math.vector_ops import clamp


def enrich_retention_decision_inputs(
    base_inputs: dict[str, float],
    behavior_observables: dict[str, float],
) -> dict[str, float]:
    result = dict(base_inputs)
    result["hazard_modifier"] = clamp(
        (behavior_observables.get("anti_field_level", 0.0) + (1.0 - behavior_observables.get("coherence_score", 0.0))) / 2.0
    )
    result["readiness_modifier"] = clamp(
        (
            behavior_observables.get("payment_readiness_level", 0.0)
            + behavior_observables.get("resonance_readiness", 0.0)
            + behavior_observables.get("timing_window_score", 0.0)
        )
        / 3.0
    )
    result["trust_modifier"] = clamp(behavior_observables.get("trust_level", 0.0))
    return result
