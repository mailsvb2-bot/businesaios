from __future__ import annotations


def inject_behavior_observables(feature_vector: dict[str, float], observables: dict[str, float]) -> dict[str, float]:
    result = dict(feature_vector)
    mapping = {
        "behavior_intent_level": observables.get("intent_level", 0.0),
        "behavior_trust_level": observables.get("trust_level", 0.0),
        "behavior_value_level": observables.get("value_recognition_level", 0.0),
        "behavior_payment_level": observables.get("payment_readiness_level", 0.0),
        "behavior_coherence": observables.get("coherence_score", 0.0),
        "behavior_oscillation": observables.get("oscillation_score", 0.0),
        "behavior_anti": observables.get("anti_field_level", 0.0),
        "behavior_resonance": observables.get("resonance_readiness", 0.0),
        "behavior_timing_window": observables.get("timing_window_score", 0.0),
        "behavior_offer_repulsion": observables.get("offer_repulsion_score", 0.0),
    }
    result.update(mapping)
    return result
