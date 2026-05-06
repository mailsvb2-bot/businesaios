from __future__ import annotations

from interfaces.api.admin_route_handlers import AdminRouteHandlers


def test_admin_route_handlers_expose_capability_diagnostics_view() -> None:
    handlers = AdminRouteHandlers()
    view = handlers.get_capability_diagnostics_view(
        tenant_id='tenant-a',
        capability_view={
            'diagnostics': {
                'status': 'blocked',
                'headline': 'Capability blocked for launch_campaign.',
                'operator_action': 'review_and_handoff',
                'signals': (
                    {'code': 'tenant_policy_blocked', 'severity': 'high', 'summary': 'Policy denied action.', 'operator_actionable': True},
                ),
            },
            'policy_verdict': {'allowed': False, 'reason': 'policy_requires_supervised_autonomy'},
            'execution_verdict': {'allowed': False, 'operator_required': True},
        },
    )
    assert view is not None
    assert view['diagnostics']['status'] == 'blocked'
    assert view['diagnostics']['signals'][0]['code'] == 'tenant_policy_blocked'
    assert view['policy_verdict']['allowed'] is False


def test_operator_run_view_includes_capability_diagnostics_when_present() -> None:
    handlers = AdminRouteHandlers()

    class _Run:
        run_id = 'run-1'
        trace_id = 'trace-1'
        status = 'running'
        stage = 'execution'

    view = handlers.get_operator_run_view(
        tenant_id='tenant-a',
        run_snapshot=_Run(),
        capability_view={'diagnostics': {'status': 'ok', 'headline': 'Capability healthy.', 'operator_action': 'none', 'signals': ()}},
    )
    assert view['capability_diagnostics']['diagnostics']['status'] == 'ok'
