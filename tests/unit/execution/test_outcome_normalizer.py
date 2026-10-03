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


def test_outcome_normalizer_preserves_phase14_observed_signals() -> None:
    normalizer = OutcomeNormalizer()
    outcome = normalizer.normalize(
        output={
            "revenue": 0,
            "converted": False,
            "margin": "14.5",
            "retention_rate": "0.72",
            "actual_cost": "5",
            "latency_ms": "125",
            "complaint": False,
            "human_override": True,
        },
        payload=None,
    )

    assert outcome["revenue_observed"] is True
    assert outcome["conversion_observed"] is True
    assert outcome["margin"] == 14.5
    assert outcome["retention_rate"] == 0.72
    assert outcome["actual_cost"] == 5.0
    assert outcome["latency_ms"] == 125.0
    assert outcome["complaint"] is False
    assert outcome["complaint_observed"] is True
    assert outcome["human_override"] is True
    assert outcome["human_override_observed"] is True


def test_outcome_normalizer_ignores_malformed_phase14_optional_metrics() -> None:
    outcome = OutcomeNormalizer().normalize(
        output={
            "margin": {"unexpected": "mapping"},
            "latency_ms": ["not", "numeric"],
        },
        payload=None,
    )

    assert "margin" not in outcome
    assert "latency_ms" not in outcome


def test_outcome_normalizer_marks_numeric_metrics_observed_only_after_valid_parsing() -> None:
    outcome = OutcomeNormalizer().normalize(
        output={
            "revenue": None,
            "conversion_rate": "N/A",
            "converted": "unknown",
        },
        payload=None,
    )

    assert outcome["revenue"] == 0.0
    assert outcome["converted"] is False
    assert "revenue_observed" not in outcome
    assert "conversion_observed" not in outcome


def test_outcome_normalizer_marks_explicit_valid_zero_and_false_as_observed() -> None:
    outcome = OutcomeNormalizer().normalize(
        output={
            "revenue": 0,
            "conversion_rate": 0,
            "converted": False,
        },
        payload=None,
    )

    assert outcome["revenue_observed"] is True
    assert outcome["conversion_observed"] is True
