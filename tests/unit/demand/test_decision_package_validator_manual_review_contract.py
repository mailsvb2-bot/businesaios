import pytest

from demand_decision.decision_package_validator import DecisionPackageValidator


class Candidate:
    business_id = 'biz-1'


def test_decision_package_validator_rejects_manual_review_with_candidates() -> None:
    with pytest.raises(ValueError):
        DecisionPackageValidator().validate({
            'request_id': 'req-1',
            'ranked_candidates': (Candidate(),),
            'trace': {},
            'requires_manual_review': True,
        })
