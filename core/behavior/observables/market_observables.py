from __future__ import annotations

from core.behavior.contracts.segment_field import SegmentField
from core.behavior.math.vector_ops import clamp, mean


def compute_market_observables(segment_fields: list[SegmentField]) -> dict[str, float]:
    if not segment_fields:
        return {
            "market_direction_vector": 0.0,
            "market_attention_density": 0.0,
            "market_coherence_score": 0.0,
            "market_trust_temperature": 0.0,
            "market_price_compression": 0.0,
            "market_novelty_wave": 0.0,
            "market_instability_index": 0.0,
        }
    return {
        "market_direction_vector": clamp(mean([s.observables.get("segment_conversion_wave", 0.0) for s in segment_fields])),
        "market_attention_density": clamp(mean([s.observables.get("segment_offer_saturation", 0.0) for s in segment_fields])),
        "market_coherence_score": clamp(mean([s.observables.get("segment_coherence", 0.0) for s in segment_fields])),
        "market_trust_temperature": clamp(mean([s.observables.get("segment_trust_drift", 0.0) for s in segment_fields])),
        "market_price_compression": clamp(mean([s.observables.get("segment_price_tension", 0.0) for s in segment_fields])),
        "market_novelty_wave": clamp(mean([s.observables.get("segment_novelty_hunger", 0.0) for s in segment_fields])),
        "market_instability_index": clamp(mean([s.observables.get("segment_fatigue_index", 0.0) for s in segment_fields])),
    }
