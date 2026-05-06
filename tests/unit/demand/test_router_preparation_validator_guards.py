import pytest

from routing.router_preparation_validator import RouterPreparationValidator


class Candidate:
    def __init__(self, business_id: str) -> None:
        self.business_id = business_id


def test_router_preparation_validator_rejects_duplicate_business_ids() -> None:
    validator = RouterPreparationValidator()
    with pytest.raises(ValueError):
        validator.validate({
            'request_id': 'req-1',
            'ranked_candidates': (Candidate('biz-1'), Candidate('biz-1')),
            'trace': {},
        })
