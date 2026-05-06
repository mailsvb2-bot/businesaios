from __future__ import annotations

from dataclasses import dataclass

from interfaces.api.action_models import ExecuteActionRequest
from interfaces.api.api_handler_bundle import build_api_handler_bundle
from interfaces.api.headless_models import ExecuteGoalRequest
from observability.action_audit_log import ActionAuditLog


class _Service:
    def __init__(self) -> None:
        self.calls = 0

    def execute_action(self, action):
        self.calls += 1
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'echo': dict(action.payload)},
        }

    def startup_audit_events(self):
        return ()


class _Contract:
    def execute_autopilot(self, request):
        return type('Report', (), {
            'goal': request.goal,
            'business_id': request.business_id,
            'tenant_id': request.tenant_id,
            'completed': True,
            'stop_reason': 'done',
            'steps': [],
            'final_feedback': {},
        })()


class _BusinessMemoryQuery:
    def get_summary(self, *, tenant_id, business_id):
        return {'tenant_id': tenant_id, 'business_id': business_id}

    def get_memory(self, *, tenant_id, business_id):
        return {'tenant_id': tenant_id, 'business_id': business_id}

    def get_recent_runs(self, *, tenant_id, business_id, limit):
        return []

    def get_recurring_failures(self, *, tenant_id, business_id):
        return []

    def get_recurring_wins(self, *, tenant_id, business_id):
        return []


@dataclass
class _Runtime:
    contract: object = _Contract()
    business_memory_query: object = _BusinessMemoryQuery()


class _DependencyContainer:
    tenant_quota_guard = None
    api_idempotency_store = None


def test_api_handler_bundle_reuses_one_runtime_provider_and_executes_action_stack() -> None:
    service = _Service()
    runtime = _Runtime()
    bundle = build_api_handler_bundle(
        application_service=service,
        dependency_container=_DependencyContainer(),
        action_audit_log=ActionAuditLog(),
        headless_runtime_provider=__import__('interfaces.api.headless_runtime_provider', fromlist=['build_headless_runtime_provider']).build_headless_runtime_provider(runtime=runtime),
    )

    response = bundle.route_handlers.execute_action(ExecuteActionRequest(action_type='launch', payload={'x': 1, 'idempotency_key': 'idem-1'}))
    assert response.status == 'ok'
    assert service.calls == 1

    goal = bundle.headless_handlers.execute_goal(ExecuteGoalRequest(goal='grow', business_id='b', tenant_id='t'))
    assert goal.completed is True

    summary = bundle.business_memory_handlers.get_summary(
        __import__('interfaces.api.business_memory_models', fromlist=['BusinessMemorySummaryRequest']).BusinessMemorySummaryRequest(tenant_id='t', business_id='b')
    )
    assert summary.tenant_id == 't'
    assert summary.business_id == 'b'
