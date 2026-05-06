from __future__ import annotations

from execution.outcome_normalizer import OutcomeNormalizer


def test_outcome_normalizer_merges_payload_seed_and_output() -> None:
    normalizer = OutcomeNormalizer()
    outcome = normalizer.normalize(
        output={"revenue": "120", "responded": 1},
        payload={"feedback_seed": {"converted": True, "terminal": False}},
    )
    assert outcome["revenue"] == 120.0
    assert outcome["responded"] is True
    assert outcome["converted"] is True
    assert outcome["customer_success"] is True


def test_outcome_normalizer_fail_closed_defaults() -> None:
    normalizer = OutcomeNormalizer()
    outcome = normalizer.normalize(output=None, payload=None)
    assert outcome["revenue"] == 0.0
    assert outcome["converted"] is False
    assert outcome["responded"] is False
