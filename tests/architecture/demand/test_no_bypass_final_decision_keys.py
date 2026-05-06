from __future__ import annotations

import pytest

from routing.router_publisher import RouterPublisher
from demand_decision.demand_decision_publisher import DemandDecisionPublisher


class Ranked:
    def __init__(self, business_id: str, rank_score: float, blocked: bool = False):
        self.business_id = business_id
        self.rank_score = rank_score
        self.blocked = blocked


def test_router_publisher_rejects_final_decision_payload() -> None:
    with pytest.raises(ValueError):
        RouterPublisher().publish({'request_id': 'r1', 'selected_business_id': 'biz-1', 'trace': {}, 'ranked_candidates': ()})


def test_legacy_demand_decision_publisher_is_retired() -> None:
    publisher = DemandDecisionPublisher()
    with pytest.raises(RuntimeError):
        publisher.publish(request=object(), intent=object(), routing_preparation={'ranked_candidates': (Ranked('biz-1', 0.9),), 'trace': {}})
