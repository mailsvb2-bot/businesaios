import pytest

from ml.policy_promotion_guard import (
    EvaluationSnapshot,
    PolicyPromotionGuard,
    PromotionBlocked,
)


def test_same_policy_cannot_be_promoted() -> None:
    guard = PolicyPromotionGuard()
    baseline = EvaluationSnapshot("p1", 1.0, 0.1, 1000)
    candidate = EvaluationSnapshot("p1", 1.2, 0.1, 1000)

    with pytest.raises(PromotionBlocked):
        guard.require_allowed(baseline, candidate)


def test_insufficient_improvement_blocks_promotion() -> None:
    guard = PolicyPromotionGuard(min_sample_size=10, min_improvement=0.05)
    baseline = EvaluationSnapshot("p1", 1.00, 0.1, 1000)
    candidate = EvaluationSnapshot("p2", 1.02, 0.1, 1000)

    with pytest.raises(PromotionBlocked):
        guard.require_allowed(baseline, candidate)


def test_good_candidate_passes() -> None:
    guard = PolicyPromotionGuard(min_sample_size=10, min_improvement=0.05)
    baseline = EvaluationSnapshot("p1", 1.00, 0.1, 1000)
    candidate = EvaluationSnapshot("p2", 1.10, 0.1, 1000)

    guard.require_allowed(baseline, candidate)
