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
    autonomy_tier: str = 'full_autonomy'
    meta: dict[str, Any] = field(default_factory=dict)


def test_router_blocks_full_autonomy_on_insufficient_evidence(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(request=StubRequest(), state=StubState(), action_type='launch_campaign', payload={'estimated_cost': 10.0})
    assert routed.allowed is False
    assert routed.reason == 'insufficient_evidence_for_full_autonomy'


def test_router_falls_back_on_stale_capability_evidence(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    for _ in range(4):
        registry.update_after_feedback(
            tenant_id='tenant-1',
            action_type='reply_to_inquiry',
            feedback={'executed': True, 'verified': True, 'finished_at': '2026-03-20T12:00:00Z'},
        )
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(request=StubRequest(autonomy_tier='bounded_autonomy'), state=StubState(), action_type='reply_to_inquiry', payload={'estimated_cost': 1.0})
    assert routed.allowed is True
    assert routed.fallback_used is True
    assert routed.action_type == 'notify_owner'
    assert routed.payload_patch['capability_fallback_reason'] == 'stale_evidence'


def test_router_allows_bounded_autonomy_bootstrap_without_verified_evidence(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(
        request=StubRequest(autonomy_tier='bounded_autonomy'),
        state=StubState(),
        action_type='launch_campaign',
        payload={'estimated_cost': 10.0},
    )
    assert routed.allowed is True
    assert routed.reason == 'capability_ok'
    assert routed.capability is not None
    assert routed.capability['runtime']['evidence_state'] == 'insufficient'
    assert routed.capability['runtime']['recommended_autonomy_tier'] == 'bounded_autonomy'
    assert routed.capability['runtime']['metadata']['bootstrap_mode'] == 'first_run_enabled_without_verified_evidence'
