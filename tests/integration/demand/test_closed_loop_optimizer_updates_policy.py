from __future__ import annotations

from demand_learning.closed_loop_optimizer import ClosedLoopOptimizer
from lead_outcomes import LeadOutcomeRegistry


def test_closed_loop_optimizer_updates_policy_from_outcomes():
    registry = LeadOutcomeRegistry()
    for index in range(12):
        registry.update(f'r{index}', {
            'business_id': 'biz-1' if index < 8 else 'biz-2',
            'converted': index < 7,
            'revenue': 120.0 if index < 8 else 40.0,
            'quality_issue': False if index < 7 else True,
        })
    optimizer = ClosedLoopOptimizer()
    state = optimizer.learn(tuple(registry.snapshot().values()))
    assert 'biz-1' in state.sample_size
    assert state.sample_size['biz-1'] == 8
    assert state.causal_bonus['biz-1'] >= state.causal_bonus.get('biz-2', 0.0)
