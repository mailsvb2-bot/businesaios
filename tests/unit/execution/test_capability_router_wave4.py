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


def _warm_capability(registry: CapabilityHealthRegistry, action_type: str) -> None:
    for idx in range(4):
        registry.update_after_feedback(
            tenant_id='tenant-1',
            action_type=action_type,
            feedback={'executed': True, 'verified': True, 'finished_at': f'2026-03-30T1{idx}:00:00Z'},
        )


def test_router_surfaces_unified_approval_verdict(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    _warm_capability(registry, 'launch_campaign')
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(
        request=StubRequest(autonomy_tier='supervised'),
        state=StubState(),
        action_type='launch_campaign',
        payload={'estimated_cost': 10.0},
    )
    assert routed.allowed is True
    verdict = routed.payload_patch['execution_verdict']
    assert verdict['approval_required'] is True
    assert verdict['allowed'] is False
    assert routed.capability['execution_verdict']['approval_required'] is True
    assert routed.capability['allowed'] is True

def test_router_blocks_on_budget_verdict(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    _warm_capability(registry, 'reply_to_inquiry')
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    request = StubRequest(
        autonomy_tier='bounded_autonomy',
        economy={'max_total_cost': 1.0},
        meta={'previous_feedback': {'action_budget_state': {'spent_total': 0.8, 'spent_this_run': 0.8}}},
    )
    routed = router.route(
        request=request,
        state=StubState(),
        action_type='reply_to_inquiry',
        payload={'estimated_cost': 1.0, 'publication_count': 1},
    )
    assert routed.allowed is False
    assert routed.reason == 'action_budget_exceeded'
    verdict = routed.payload_patch['execution_verdict']
    assert verdict['budget_allowed'] is False
    assert verdict['budget']['allowed'] is False


def test_router_blocks_on_blast_radius_verdict(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    _warm_capability(registry, 'reply_to_inquiry')
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    request = StubRequest(
        autonomy_tier='bounded_autonomy',
        constraints={'blast_radius_max_outbound_per_window': 1},
    )
    routed = router.route(
        request=request,
        state=StubState(),
        action_type='reply_to_inquiry',
        payload={'recipient_count': 2},
    )
    assert routed.allowed is False
    assert routed.reason == 'blast_radius_exceeded'
    verdict = routed.payload_patch['execution_verdict']
    assert verdict['blast_radius_allowed'] is False
    assert verdict['blast_radius']['allowed'] is False
