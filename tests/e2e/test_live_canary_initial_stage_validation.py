from __future__ import annotations

from dataclasses import replace

from config.live_canary_policy import LiveCanaryPolicy


def valid_policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="initial-stage-validation",
        candidate_policy_id="candidate@v2",
        assignment_secret="s" * 32,
        candidate_pct=1.0,
        max_candidate_pct=10.0,
        initial_canary_pct=1,
        allowed_tenant_ids=("tenant-a",),
    )


def test_initial_stage_must_be_positive_and_bounded() -> None:
    policy = valid_policy()

    assert "initial_canary_pct_out_of_range" in replace(
        policy, initial_canary_pct=0
    ).validate()
    assert "initial_canary_pct_out_of_range" in replace(
        policy, initial_canary_pct=101
    ).validate()


def test_initial_stage_cannot_exceed_maximum_rollout() -> None:
    policy = replace(valid_policy(), max_candidate_pct=5.0, initial_canary_pct=10)

    assert "initial_canary_pct_exceeds_maximum" in policy.validate()


def test_non_finite_cost_and_statistical_limits_fail_closed() -> None:
    policy = valid_policy()

    assert "max_daily_cost_must_be_non_negative" in replace(
        policy, max_daily_cost=float("inf")
    ).validate()
    assert "max_cost_per_outcome_ratio_must_be_at_least_one" in replace(
        policy, max_cost_per_outcome_ratio=float("nan")
    ).validate()
    assert "max_sample_ratio_z_must_be_positive" in replace(
        policy, max_sample_ratio_z=float("nan")
    ).validate()


def test_non_finite_poll_interval_and_rates_fail_closed() -> None:
    policy = valid_policy()

    assert "outcome_poll_seconds_must_be_at_least_one" in replace(
        policy, outcome_poll_seconds=float("nan")
    ).validate()
    assert "max_error_rate_out_of_range" in replace(
        policy, max_error_rate=float("nan")
    ).validate()
    assert "max_complaint_rate_out_of_range" in replace(
        policy, max_complaint_rate=float("inf")
    ).validate()
