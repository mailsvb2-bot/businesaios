from __future__ import annotations

import pytest

from demand_decision.decision_package_validator import DecisionPackageValidator


def test_decision_package_validator_rejects_noncanonical_target() -> None:
    validator = DecisionPackageValidator()
    with pytest.raises(ValueError, match='optimization_target must be canonical'):
        validator.validate({
            'ranked_candidates': (),
            'trace': {'optimization_target': 'other_target'},
        })
