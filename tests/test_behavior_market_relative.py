from __future__ import annotations

from core.behavior.market.market_relative_state import compute_market_relative_person_state


def test_compute_market_relative_person_state_contains_alignment_scores() -> None:
    result = compute_market_relative_person_state(
        {"payment_readiness_level": 0.8, "trust_level": 0.7, "coherence_score": 0.9},
        {"segment_conversion_wave": 0.6, "segment_coherence": 0.7},
        {
            "market_direction_vector": 0.5,
            "market_coherence_score": 0.6,
            "market_trust_temperature": 0.65,
        },
    )
    assert result["market_alignment_score"] >= 0.0
    assert result["segment_alignment_score"] >= 0.0
