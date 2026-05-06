from __future__ import annotations

from config.execution_contract import CANONICAL_OPTIMIZATION_TARGET
from contracts.matching.routing_decision import RoutingDecision


class DemandDecisionContractMapper:
    """Compatibility-only preview mapper.

    This class is intentionally non-executable: it never selects a winner and
    never emits a final runnable decision. It exists only to preserve old
    interfaces while forcing callers back into the canonical DecisionCore path.
    """

    def map(self, *, request_id: str, candidates: tuple[object, ...], routing_trace: dict[str, object]) -> RoutingDecision:
        trace = dict(routing_trace)
        trace['decision_path'] = 'demand_decision_required'
        trace['optimization_target'] = CANONICAL_OPTIMIZATION_TARGET
        trace['candidate_count'] = len(tuple(candidates or ()))
        trace['manual_review_reason'] = str(trace.get('manual_review_reason') or 'compatibility_mapper_requires_decision_core')
        return RoutingDecision(
            request_id=str(request_id),
            selected_business_id=None,
            runner_up_business_ids=(),
            trace=trace,
            requires_manual_review=True,
        )
