from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.capability_matrix import CapabilityMatrix
from execution.capability_tenant_policy import CapabilityTenantPolicyService


@dataclass(frozen=True)
class StubRequest:
    tenant_id: str = 'tenant-1'
    business_id: str = 'business-1'
    autonomy_tier: str = 'full_autonomy'
    channel: str = 'headless'
    region: str = 'global'
    constraints: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def test_tenant_policy_blocks_business_override_action_type() -> None:
    matrix = CapabilityMatrix()
    record = matrix.record_for_action(action_type='launch_campaign', runtime_capabilities={})
    service = CapabilityTenantPolicyService()
    request = StubRequest(
        meta={
            'capability_policy': {
                'business_overrides': {
                    'business-1': {
                        'disabled_action_types': ['launch_campaign'],
                    }
                }
            }
        }
    )
    verdict = service.evaluate(request=request, record=record)
    assert verdict.allowed is False
    assert verdict.reason == 'action_type_disabled_by_policy'
    assert verdict.policy_scope == 'business:business-1'


def test_tenant_policy_restricts_full_autonomy_for_supervised_only_capability() -> None:
    matrix = CapabilityMatrix()
    record = matrix.record_for_action(action_type='launch_campaign', runtime_capabilities={})
    service = CapabilityTenantPolicyService()
    request = StubRequest(meta={'capability_policy': {'supervised_only_capability_keys': ['ads_write']}})
    verdict = service.evaluate(request=request, record=record)
    assert verdict.allowed is False
    assert verdict.reason == 'policy_requires_supervised_autonomy'
    assert verdict.recommended_autonomy_tier == 'supervised'
