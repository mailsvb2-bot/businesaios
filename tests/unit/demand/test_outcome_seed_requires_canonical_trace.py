import pytest

from demand_learning.closed_loop_optimizer import ClosedLoopOptimizer
from demand_os.outcome_recorder import DemandOutcomeRecorder
from lead_outcomes import LeadOutcomeRegistry


class Request:
    request_id = 'req-1'
    customer_id = 'c-1'
    created_at_ms = 1


class Decision:
    selected_business_id = 'biz-1'
    requires_manual_review = False
    trace = {'decision_path': 'shadow.path'}


class Delivery:
    delivery_status = 'delivered'
    channel = 'crm'
    delivered_at_ms = 2


def test_outcome_seed_rejects_noncanonical_routed_trace() -> None:
    recorder = DemandOutcomeRecorder(outcomes=LeadOutcomeRegistry(), optimizer=ClosedLoopOptimizer())
    with pytest.raises(ValueError):
        recorder.seed(request=Request(), decision=Decision(), delivery=Delivery())
