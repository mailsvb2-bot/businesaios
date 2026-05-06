from __future__ import annotations

from demand_learning.policy_promotion import PolicyPromotion
from demand_learning.policy_rollback import PolicyRollback


def test_policy_promotion_requires_sample_size() -> None:
    assert not PolicyPromotion().allow({'offline_conversion_rate': 0.9, 'sample_size': 1})


def test_policy_rollback_requires_sample_size() -> None:
    assert not PolicyRollback().allow({'offline_conversion_rate': 0.0, 'offline_bad_outcome_rate': 1.0, 'sample_size': 1})
