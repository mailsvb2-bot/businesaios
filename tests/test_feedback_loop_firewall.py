import pytest

from learning.replay import (
    FeedbackLoopFirewall,
    FeedbackLoopViolation,
    PolicyMetadata,
)


def test_dataset_separation_is_required() -> None:
    firewall = FeedbackLoopFirewall()

    with pytest.raises(FeedbackLoopViolation):
        firewall.validate_dataset_separation("dataset_a", "dataset_a")


def test_policy_cannot_be_evaluated_on_training_dataset() -> None:
    firewall = FeedbackLoopFirewall()
    policy = PolicyMetadata(
        policy_id="p1",
        trained_at_ms=0,
        source_dataset_id="dataset_a",
    )

    with pytest.raises(FeedbackLoopViolation):
        firewall.validate_policy_eval_dataset(policy, "dataset_a")


def test_eval_delay_is_enforced() -> None:
    firewall = FeedbackLoopFirewall(min_eval_delay_ms=1000)
    policy = PolicyMetadata(
        policy_id="p1",
        trained_at_ms=5000,
        source_dataset_id="dataset_a",
    )

    with pytest.raises(FeedbackLoopViolation):
        firewall.validate_eval_delay(policy, now_ms=5500)
