from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from execution.headless_contract import HeadlessExecutionContract
from application.headless.models import GoalExecutionRequest
from runtime.execution.executor_result import ExecutionResult

opt_mod = pytest.importorskip('execution.optimization')
AdaptiveOptimizationService = opt_mod.AdaptiveOptimizationService
AdaptiveOptimizer = opt_mod.AdaptiveOptimizer
FilePerformanceProfileStore = opt_mod.FilePerformanceProfileStore


@dataclass(frozen=True)
class _Decision:
    decision_id: str = 'dec-1'
    action: str = 'launch_campaign'
    payload: dict[str, Any] = field(default_factory=lambda: {'estimated_cost': 10.0})
    correlation_id: str = 'corr-1'


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision


@dataclass(frozen=True)
class _WorldState:
    meta: dict[str, Any] = field(default_factory=dict)


class StubDecisionCore:
    def optimize(self, state: Any) -> _Envelope:
        return _Envelope(decision=_Decision())


class StubStateMapper:
    def to_world_state(self, *, request: Any, step_index: int, previous_feedback: dict[str, Any]) -> _WorldState:
        return _WorldState(meta={'runtime_capabilities': {'launch_campaign': {'enabled': True}}})


class StubExecutor:
    def execute(self, env: Any) -> ExecutionResult:
        return ExecutionResult(ok=True, output={'verified': True, 'goal_reached': True, 'verification_confidence': 0.95, 'verification_status': 'verified', 'external_refs': ['proof://1'], 'latency_ms': 750.0, 'revenue_outcome': {'delta': 40.0}}, error=None, decision_id=str(env.decision.decision_id), correlation_id=str(env.decision.correlation_id))


class StubFeedbackReader:
    def read(self, **kwargs: Any) -> dict[str, Any]:
        result = kwargs['result']
        output = dict(getattr(result, 'output', {}) or {})
        return {'executed': bool(getattr(result, 'ok', False)), 'verified': bool(output.get('verified', False)), 'goal_reached': bool(output.get('goal_reached', False)), 'verification_confidence': float(output.get('verification_confidence', 0.0)), 'verification_status': str(output.get('verification_status', 'failed')), 'external_refs': list(output.get('external_refs') or []), 'latency_ms': float(output.get('latency_ms', 0.0))}


def test_closed_loop_exposes_adaptive_optimization_context_and_feedback(tmp_path: Path) -> None:
    supported = set(inspect.signature(HeadlessExecutionContract.__init__).parameters)
    if 'adaptive_optimization_service' not in supported:
        pytest.skip('HeadlessExecutionContract does not support adaptive_optimization_service')
    service = AdaptiveOptimizationService(optimizer=AdaptiveOptimizer(store=FilePerformanceProfileStore(root_dir=tmp_path / 'adaptive')))
    contract = HeadlessExecutionContract(decision_core=StubDecisionCore(), executor=StubExecutor(), state_mapper=StubStateMapper(), feedback_reader=StubFeedbackReader(), adaptive_optimization_service=service)
    request = GoalExecutionRequest(goal='increase revenue', business_id='biz-1', tenant_id='tenant-1', max_steps=1, autonomy_tier='bounded_autonomy', meta={'preferred_action_type': 'launch_campaign'})
    report = contract.execute_autopilot(request)
    assert 'adaptive_optimization' in report.final_feedback
    context = dict(report.final_feedback['adaptive_optimization'])
    assert context['evidence_only'] is True
    assert context['must_not_issue_decision'] is True
