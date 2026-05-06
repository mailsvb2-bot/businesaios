from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.capability_health_registry import CapabilityHealthRegistry
from execution.capability_health_scoring import FileCapabilityHealthStore
from execution.capability_matrix import CapabilityMatrix
from execution.capability_router import ExecutionCapabilityRouter


@dataclass(frozen=True)
class StubState:
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StubRequest:
    tenant_id: str = 'tenant-1'
    autonomy_tier: str = 'supervised'
    approval_policy: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def test_router_surfaces_operator_diagnostics_for_stale_capability(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    registry.update_after_feedback(
        tenant_id='tenant-1',
        action_type='launch_campaign',
        feedback={'executed': True, 'verified': True, 'finished_at': '2026-03-20T10:00:00Z'},
    )
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(
        request=StubRequest(autonomy_tier='bounded_autonomy'),
        state=StubState(),
        action_type='launch_campaign',
        payload={'estimated_cost': 5.0},
    )
    assert routed.fallback_used is True
    diagnostics = routed.capability['diagnostics']
    assert diagnostics['status'] in {'fallback', 'watch'}
    codes = {signal['code'] for signal in diagnostics['signals']}
    assert 'stale_evidence' in codes
    assert routed.payload_patch['capability_diagnostics']['operator_action'] == 'review_and_handoff'


def test_router_surfaces_budget_diagnostics_when_blocked(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    for idx in range(4):
        registry.update_after_feedback(
            tenant_id='tenant-1',
            action_type='reply_to_inquiry',
            feedback={'executed': True, 'verified': True, 'finished_at': f'2026-03-30T1{idx}:00:00Z'},
        )
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(
        request=StubRequest(
            autonomy_tier='bounded_autonomy',
            economy={'max_total_cost': 1.0},
            meta={'previous_feedback': {'action_budget_state': {'spent_total': 0.8, 'spent_this_run': 0.8}}},
        ),
        state=StubState(),
        action_type='reply_to_inquiry',
        payload={'estimated_cost': 1.0, 'publication_count': 1},
    )
    assert routed.allowed is False
    diagnostics = routed.capability['diagnostics']
    codes = {signal['code'] for signal in diagnostics['signals']}
    assert 'budget_blocked' in codes
    assert diagnostics['operator_action'] == 'review_and_handoff'
