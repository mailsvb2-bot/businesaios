from __future__ import annotations

from core.behavior.integration.retention_hazard_bridge import adjust_hazard_score
from core.behavior.integration.retention_readiness_bridge import adjust_readiness_score


def test_adjust_hazard_score_increases_with_anti() -> None:
    high = adjust_hazard_score(
        0.4,
        {"anti_field_level": 0.8, "fatigue_score": 0.6, "coherence_score": 0.2},
    )
    low = adjust_hazard_score(
        0.4,
        {"anti_field_level": 0.1, "fatigue_score": 0.1, "coherence_score": 0.9},
    )
    assert high >= low


def test_adjust_readiness_score_penalizes_anti() -> None:
    high = adjust_readiness_score(
        0.5,
        {
            "trust_level": 0.8,
            "payment_readiness_level": 0.7,
            "resonance_readiness": 0.9,
            "anti_field_level": 0.0,
        },
    )
    low = adjust_readiness_score(
        0.5,
        {
            "trust_level": 0.8,
            "payment_readiness_level": 0.7,
            "resonance_readiness": 0.9,
            "anti_field_level": 0.8,
        },
    )
    assert high >= low
