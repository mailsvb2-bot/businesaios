from __future__ import annotations

from core.behavior.contracts.person_field import PersonField
from core.behavior.math.vector_ops import clamp, mean


def compute_segment_observables(person_fields: list[PersonField]) -> dict[str, float]:
    if not person_fields:
        return {
            "segment_trust_drift": 0.0,
            "segment_price_tension": 0.0,
            "segment_conversion_wave": 0.0,
            "segment_fatigue_index": 0.0,
            "segment_offer_saturation": 0.0,
            "segment_novelty_hunger": 0.0,
            "segment_coherence": 0.0,
        }
    trust = [p.dynamic_observables.get("trust_level", 0.0) for p in person_fields]
    readiness = [p.dynamic_observables.get("payment_readiness_level", 0.0) for p in person_fields]
    fatigue = [p.dynamic_observables.get("fatigue_score", 0.0) for p in person_fields]
    coherence = [p.dynamic_observables.get("coherence_score", 0.0) for p in person_fields]
    return {
        "segment_trust_drift": clamp(mean([p.dynamic_observables.get("trust_velocity", 0.0) for p in person_fields])),
        "segment_price_tension": clamp(mean([max(0.0, r - t) for r, t in zip(readiness, trust, strict=False)])),
        "segment_conversion_wave": clamp(mean([p.dynamic_observables.get("conversion_window_score", 0.0) for p in person_fields])),
        "segment_fatigue_index": clamp(mean(fatigue)),
        "segment_offer_saturation": clamp(mean([p.dynamic_observables.get("offer_repulsion_score", 0.0) for p in person_fields])),
        "segment_novelty_hunger": clamp(mean([1.0 - p.dynamic_observables.get("value_recognition_level", 0.0) for p in person_fields])),
        "segment_coherence": clamp(mean(coherence)),
    }
