from __future__ import annotations

from execution.capability_operator_view import normalize_capability_view


def test_normalize_capability_view_accepts_feedback_payload_shape() -> None:
    view = normalize_capability_view(
        {
            'tenant_id': 'tenant-a',
            'capability_diagnostics': {'status': 'blocked', 'headline': 'Blocked', 'operator_action': 'review_and_handoff', 'signals': ()},
            'execution_verdict': {'allowed': False, 'operator_required': True},
            'policy_verdict': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
        }
    )
    assert view['tenant_id'] == 'tenant-a'
    assert view['diagnostics']['status'] == 'blocked'
    assert view['execution_verdict']['operator_required'] is True
    assert view['policy_verdict']['allowed'] is False


def test_normalize_capability_view_accepts_compat_planning_shape() -> None:
    view = normalize_capability_view(
        {
            'capability_planning': {
                'allowed': False,
                'fallback_used': True,
                'reason': 'degraded_mode_notify_owner',
                'capability': {
                    'diagnostics': {'status': 'fallback', 'headline': 'Fallback', 'operator_action': 'monitor', 'signals': ()},
                    'execution_verdict': {'allowed': True},
                    'policy_verdict': {'allowed': True},
                },
            }
        }
    )
    assert view['diagnostics']['status'] == 'fallback'
    assert view['capability']['allowed'] is False
    assert view['capability']['fallback_used'] is True
    assert view['capability']['reason'] == 'degraded_mode_notify_owner'
