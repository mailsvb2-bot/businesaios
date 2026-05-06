from __future__ import annotations

from core.behavior.math.vector_ops import clamp


def compute_market_relative_person_state(
    person_observables: dict[str, float],
    segment_observables: dict[str, float] | None,
    market_observables: dict[str, float] | None,
) -> dict[str, float]:
    segment_observables = segment_observables or {}
    market_observables = market_observables or {}

    person_readiness = person_observables.get("payment_readiness_level", 0.0)
    person_trust = person_observables.get("trust_level", 0.0)
    person_coherence = person_observables.get("coherence_score", 0.0)

    segment_wave = segment_observables.get("segment_conversion_wave", 0.0)
    segment_coherence = segment_observables.get("segment_coherence", 0.0)
    market_direction = market_observables.get("market_direction_vector", 0.0)
    market_coherence = market_observables.get("market_coherence_score", 0.0)

    return {
        "segment_alignment_score": clamp(1.0 - abs(person_readiness - segment_wave)),
        "market_alignment_score": clamp(1.0 - abs(person_readiness - market_direction)),
        "segment_phase_delta": clamp(abs(person_coherence - segment_coherence)),
        "market_phase_delta": clamp(abs(person_coherence - market_coherence)),
        "ahead_of_segment_score": clamp(max(0.0, person_readiness - segment_wave)),
        "ahead_of_market_score": clamp(max(0.0, person_readiness - market_direction)),
        "trust_vs_market_gap": clamp(abs(person_trust - market_observables.get("market_trust_temperature", 0.0))),
    }
