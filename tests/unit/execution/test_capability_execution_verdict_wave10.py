from __future__ import annotations

from types import SimpleNamespace

from execution.capability_execution_verdict import CapabilityExecutionVerdictBuilder


def test_execution_verdict_treats_policy_deny_as_blocked_by_policy() -> None:
    verdict = CapabilityExecutionVerdictBuilder().build(
        request=SimpleNamespace(autonomy_tier='full_autonomy', approval_policy={}, constraints={}, tenant_id='tenant-a', meta={}),
        action_type='launch_campaign',
        payload={},
        capability_allowed=False,
        policy_verdict={'allowed': False, 'reason': 'tenant_capability_policy_denied', 'operator_required': True, 'policy_scope': 'tenant'},
    ).to_dict()

    assert verdict['allowed'] is False
    assert verdict['blocked_by_policy'] is True
    assert verdict['operator_required'] is True
    assert verdict['reason'] == 'tenant_capability_policy_denied'
    assert verdict['approval']['policy_scope'] == 'tenant'
