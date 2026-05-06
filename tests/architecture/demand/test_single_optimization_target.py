from __future__ import annotations

from config.execution_contract import CANONICAL_OPTIMIZATION_TARGET
from demand_decision.demand_decision_contract_mapper import DemandDecisionContractMapper


class Candidate:
    def __init__(self, business_id: str, blocked: bool = False) -> None:
        self.business_id = business_id
        self.blocked = blocked


def test_decision_trace_carries_single_optimization_target() -> None:
    mapper = DemandDecisionContractMapper()
    decision = mapper.map(request_id='req-1', candidates=(Candidate('biz-1'),), routing_trace={})
    assert decision.trace['optimization_target'] == CANONICAL_OPTIMIZATION_TARGET
    assert decision.selected_business_id is None
