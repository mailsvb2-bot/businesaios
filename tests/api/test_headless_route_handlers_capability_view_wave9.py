from __future__ import annotations

from types import SimpleNamespace

from interfaces.api.headless_route_handlers import HeadlessRouteHandlers
from application.headless.models import GoalExecutionReport, GoalExecutionStep


def test_execute_goal_response_exposes_normalized_capability_view(monkeypatch) -> None:
    report = GoalExecutionReport(
        goal='grow',
        business_id='biz-1',
        tenant_id='tenant-a',
        completed=False,
        stop_reason='operator_required',
        steps=(
            GoalExecutionStep(
                step_index=0,
                decision_id='d-1',
                action_id='a-1',
                action='notify_owner',
                status='blocked_by_policy',
                attempted=True,
                executed=False,
                verified=False,
                operator_required=True,
                payload={
                    'capability_diagnostics': {'status': 'blocked', 'headline': 'Blocked', 'operator_action': 'handoff', 'signals': ()},
                    'execution_verdict': {'allowed': False, 'operator_required': True},
                    'policy_verdict': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
                    'capability_planning': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
                },
                feedback={'operator_required': True},
            ),
        ),
        final_feedback={
            'capability_view': {
                'diagnostics': {'status': 'blocked', 'headline': 'Blocked', 'operator_action': 'handoff', 'signals': ()},
                'execution_verdict': {'allowed': False, 'operator_required': True},
                'policy_verdict': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
            }
        },
    )

    class _Runtime:
        contract = SimpleNamespace(execute_autopilot=lambda request: report)

    monkeypatch.setattr('interfaces.api.headless_route_handlers.build_headless_runtime', lambda: _Runtime())
    handlers = HeadlessRouteHandlers()
    request = SimpleNamespace(goal='grow', business_id='biz-1', tenant_id='tenant-a', user_id=None, region='global', max_steps=1, profile={}, signals=[], constraints={}, economy={}, meta={}, ceo=SimpleNamespace(enabled=False, objective=None, horizon='30d', risk_level='conservative'))

    response = handlers.execute_goal(request)

    assert response.steps[0].capability_view['diagnostics']['status'] == 'blocked'
    assert response.steps[0].capability_view['execution_verdict']['operator_required'] is True
    assert response.capability_view['policy_verdict']['reason'] == 'tenant_capability_policy_denied'
