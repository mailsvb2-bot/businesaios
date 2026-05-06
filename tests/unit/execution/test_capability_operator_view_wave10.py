from __future__ import annotations

from execution.capability_operator_view import normalize_capability_view


def test_normalize_capability_view_merges_nested_and_root_surfaces() -> None:
    view = normalize_capability_view(
        {
            'capability_view': {
                'diagnostics': {'status': 'blocked', 'headline': 'Nested blocked', 'signals': ({'code': 'nested'},)},
                'execution_verdict': {'allowed': False, 'operator_required': True},
            },
            'policy_verdict': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
            'capability_planning': {'allowed': False, 'fallback_used': True, 'reason': 'policy_requires_supervised_autonomy'},
        }
    )

    assert view['diagnostics']['status'] == 'blocked'
    assert view['execution_verdict']['operator_required'] is True
    assert view['policy_verdict']['reason'] == 'tenant_capability_policy_denied'
    assert view['capability']['fallback_used'] is True
    assert view['capability']['reason'] == 'policy_requires_supervised_autonomy'
