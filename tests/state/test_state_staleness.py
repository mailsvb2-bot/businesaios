from __future__ import annotations

from runtime.state.state_contract import StateObservation
from runtime.state.state_freshness_policy import FieldFreshnessPolicy, StateFreshnessPolicy


def test_state_staleness_marks_observation_as_stale_when_ttl_exceeded() -> None:
    policy = StateFreshnessPolicy(default_ttl_ms=1_000)

    decision = policy.evaluate(
        now_ms=5_000,
        observation=StateObservation(
            field_path="market.temperature",
            value=21,
            source="weather",
            observed_at_ms=3_000,
        ),
    )

    assert decision.status == "stale"
    assert decision.reason == "beyond_ttl"


def test_state_staleness_allows_authoritative_observation_to_degrade_gracefully() -> None:
    policy = StateFreshnessPolicy(
        prefix_policies={"finance": FieldFreshnessPolicy(ttl_ms=1_000, allow_stale_if_authoritative=True)}
    )

    decision = policy.evaluate(
        now_ms=10_000,
        observation=StateObservation(
            field_path="finance.balance",
            value=500,
            source="ledger",
            observed_at_ms=1_000,
            authoritative=True,
        ),
    )

    assert decision.status == "stale_authoritative"
    assert decision.reason == "beyond_ttl_but_authoritative"


def test_business_validity_boundaries_override_ttl_freshness() -> None:
    policy = StateFreshnessPolicy(default_ttl_ms=10_000)
    cases = (
        (StateObservation("x", 1, "s", 1_000, valid_from_ms=2_500), "not_yet_valid", "before_valid_from"),
        (StateObservation("x", 1, "s", 1_000, valid_until_ms=1_500), "expired", "after_valid_until"),
        (StateObservation("x", 1, "s", 1_000, superseded_at_ms=1_500), "superseded", "superseded_at_reached"),
    )
    for observation, status, reason in cases:
        decision = policy.evaluate(now_ms=2_000, observation=observation)
        assert decision.status == status
        assert decision.reason == reason
