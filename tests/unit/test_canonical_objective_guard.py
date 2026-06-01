import pytest

from core.constraints.decision import DecisionConstraints


def test_non_canonical_objective_is_rejected():
    with pytest.raises(ValueError):
        DecisionConstraints(objective_name='ctr_growth').validate()
