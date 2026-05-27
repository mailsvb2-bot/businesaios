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
    autonomy_tier: str = 'bounded_autonomy'
    meta: dict[str, Any] = field(default_factory=dict)


def test_capability_registry_maps_action_to_capability_storage(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    registry.update_after_feedback(
        tenant_id='tenant-1',
        action_type='launch_campaign',
        feedback={'executed': False, 'verified': False, 'self_healing_retry': {'reason': 'rate_limit_retry'}, 'finished_at': '2026-03-30T18:00:00Z'},
    )
    payload = registry.runtime_payload_for_action(tenant_id='tenant-1', action_type='launch_campaign')
    assert payload['capability_key'] == matrix.descriptor_for_action('launch_campaign').capability_key
    assert payload['updated_at'] == '2026-03-30T18:00:00Z'


def test_capability_router_uses_registry_overlay_for_disabled_comms(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    # Force unhealthy/disabled comms capability by repeated blocked outcomes.
    for _ in range(4):
        registry.update_after_feedback(
            tenant_id='tenant-1',
            action_type='reply_to_inquiry',
            feedback={'blocked_by_policy': True, 'reason': 'connector_disabled'},
        )
    state = StubState(meta={})
    request = StubRequest()
    router = ExecutionCapabilityRouter(matrix=matrix, health_registry=registry)
    routed = router.route(request=request, state=state, action_type='reply_to_inquiry', payload={'recipient_count': 1})
    assert routed.allowed is True
    assert routed.fallback_used is True
    assert routed.action_type == 'notify_owner'
