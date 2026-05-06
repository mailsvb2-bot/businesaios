import pytest

from ml.policy_rollout_manager import PolicyRolloutManager, RolloutGuardViolation


def test_candidate_must_differ_from_baseline() -> None:
    manager = PolicyRolloutManager()

    with pytest.raises(RolloutGuardViolation):
        manager.start_rollout(
            rollout_id="r1",
            baseline_policy_id="p1",
            candidate_policy_id="p1",
            traffic_fraction=0.1,
            now_ms=1000,
        )


def test_soak_period_is_required_before_promotion() -> None:
    manager = PolicyRolloutManager(soak_period_ms=1000)
    manager.start_rollout(
        rollout_id="r1",
        baseline_policy_id="p1",
        candidate_policy_id="p2",
        traffic_fraction=0.1,
        now_ms=1000,
    )

    with pytest.raises(RolloutGuardViolation):
        manager.promote("r1", now_ms=1500)


def test_promotion_after_soak_period() -> None:
    manager = PolicyRolloutManager(soak_period_ms=1000)
    manager.start_rollout(
        rollout_id="r1",
        baseline_policy_id="p1",
        candidate_policy_id="p2",
        traffic_fraction=0.1,
        now_ms=1000,
    )

    promoted = manager.promote("r1", now_ms=2500)
    assert promoted == "p2"
