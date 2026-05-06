from demand_learning.closed_loop_optimizer import ClosedLoopOptimizer
from demand_os.outcome_recorder import DemandOutcomeRecorder
from lead_outcomes import LeadOutcomeRegistry


class _Request:
    request_id = 'r1'
    customer_id = 'c1'
    created_at_ms = 100


class _Decision:
    selected_business_id = 'b1'
    requires_manual_review = False
    trace = {'decision_path': 'core.ai.decision_core'}


class _Delivery:
    delivery_status = 'accepted'
    channel = 'crm'
    delivered_at_ms = None


def test_outcome_timeline_keeps_seed_and_final_history() -> None:
    registry = LeadOutcomeRegistry()
    recorder = DemandOutcomeRecorder(outcomes=registry, optimizer=ClosedLoopOptimizer())

    recorder.seed(request=_Request(), decision=_Decision(), delivery=_Delivery())
    seeded = registry.require('r1')
    assert seeded['timeline'] == ['seed:accepted']

    recorder.record(request_id='r1', converted=False, revenue=0.0)
    final = registry.require('r1')
    assert final['timeline'] == ['seed:accepted', 'final:closed']
