from __future__ import annotations

from interfaces.api.response_presenter import (
    present_blocked_execute_action_response,
    present_execute_action_response,
)


def test_present_execute_action_response_preserves_details_and_normalizes_capability_view() -> None:
    response = present_execute_action_response(
        {
            'status': 'blocked',
            'action_type': 'launch_campaign',
            'reason': 'tenant_capability_policy_denied',
            'details': {
                'policy_verdict': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
                'execution_verdict': {'allowed': False, 'operator_required': True},
                'capability_diagnostics': {'status': 'blocked', 'headline': 'Blocked', 'operator_action': 'handoff'},
            },
        }
    )

    assert response.details['policy_verdict']['allowed'] is False
    assert response.capability_view['diagnostics']['status'] == 'blocked'
    assert response.capability_view['execution_verdict']['operator_required'] is True
    assert response.capability_view['policy_verdict']['reason'] == 'tenant_capability_policy_denied'


def test_present_execute_action_response_does_not_duplicate_explicit_capability_view_into_details() -> None:
    response = present_execute_action_response(
        {
            'status': 'blocked',
            'action_type': 'launch_campaign',
            'reason': 'policy_blocked',
            'capability_view': {
                'policy_verdict': {'allowed': False, 'reason': 'policy_blocked'},
            },
        }
    )

    assert 'capability_view' not in response.details
    assert response.capability_view['policy_verdict']['allowed'] is False


def test_present_blocked_execute_action_response_uses_canonical_presenter() -> None:
    response = present_blocked_execute_action_response(
        action_type='launch_campaign',
        reason='quota_exceeded',
        details={'control_plane_stage': 'quota_blocked'},
        capability_view={'policy_verdict': {'allowed': False, 'reason': 'quota_exceeded'}},
    )

    assert response.status == 'blocked'
    assert response.details['control_plane_stage'] == 'quota_blocked'
    assert response.capability_view['policy_verdict']['reason'] == 'quota_exceeded'
