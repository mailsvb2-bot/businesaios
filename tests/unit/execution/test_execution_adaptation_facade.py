from __future__ import annotations

from execution.execution_adaptation_facade import ExecutionAdaptationFacade


def test_execution_adaptation_facade_builds_learning_context() -> None:
    facade = ExecutionAdaptationFacade()
    context = facade.build_context(
        tenant_id='tenant-1',
        business_id='biz-1',
        goal_family='revenue_growth',
        counters={'total_steps': 4, 'executed_steps': 3, 'verified_steps': 2, 'achieved_steps': 1},
        spent_total=5.0,
        capability_counters={'attempts': 4, 'executed': 3, 'verified': 2, 'transient_failures': 1, 'blocked': 0, 'terminal_failures': 0},
        strategy_feedback={'approval_required': True},
        strategy_metadata={'requires_approval': True},
    )
    assert context['goal_family'] == 'revenue_growth'
    assert context['budget_posture'] in {'neutral', 'tighten', 'expand_carefully'}
    assert 'budget_posture_detail' in context
    assert context['strategy_hints']
