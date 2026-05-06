from __future__ import annotations

from interfaces.api.action_models import ExecuteActionRequest
from interfaces.api.api_handler_bundle import build_api_handler_bundle
from interfaces.api.execute_action_api_stack import build_execute_action_api_stack
from interfaces.api.execute_action_handler import build_execute_action_handler
from interfaces.api.execute_action_port_provider import build_execute_action_port_provider
from observability.action_audit_log import ActionAuditLog
from runtime.execution.decision_execution_service import build_decision_execution_service


class _Service:
    def __init__(self) -> None:
        self.calls = 0

    def execute_action(self, action, **kwargs):
        self.calls += 1
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'payload': dict(action.payload), 'kwargs': kwargs},
        }

    def startup_audit_events(self):
        return ()


class _DependencyContainer:
    tenant_quota_guard = None
    api_idempotency_store = None


class _Executor:
    def __init__(self) -> None:
        self.last = None

    def execute(self, envelope):
        self.last = envelope
        return {'status': 'ok', 'envelope': envelope}


class _DecisionCommand:
    def __init__(self) -> None:
        self.validated = False

    def validate(self):
        self.validated = True

    def to_signed_envelope(self, keyring):
        return {'signed_with': keyring, 'validated': self.validated}


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


class _Runtime:
    contract = _Contract()
    business_memory_query = _BusinessMemoryQuery()


def test_execute_action_owner_builders_preserve_canonical_stack() -> None:
    service = _Service()
    handler = build_execute_action_handler(application_service=service)
    response = handler.handle(ExecuteActionRequest(action_type='launch', payload={'x': 1}))
    assert response.status == 'ok'
    assert service.calls == 1

    stack = build_execute_action_api_stack(application_service=service)
    response2 = stack.handle(ExecuteActionRequest(action_type='ship', payload={'y': 2, 'idempotency_key': 'idem-stack'}))
    assert response2.status == 'ok'
    assert service.calls == 2


def test_execute_action_port_provider_builds_one_port_for_bundle_reuse() -> None:
    service = _Service()
    provider = build_execute_action_port_provider(
        application_service=service,
        dependency_container=_DependencyContainer(),
        action_audit_log=ActionAuditLog(),
    )
    port = provider.build_port()
    assert port is not None
    response = port.handle(ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-1'}))
    assert response.status == 'ok'

    bundle = build_api_handler_bundle(
        application_service=service,
        dependency_container=_DependencyContainer(),
        action_audit_log=ActionAuditLog(),
        headless_runtime_provider=__import__('interfaces.api.headless_runtime_provider', fromlist=['build_headless_runtime_provider']).build_headless_runtime_provider(runtime=_Runtime()),
    )
    assert bundle.execute_action_port_provider is not None
    assert bundle.route_handlers.execute_action(ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-2'})).status == 'ok'


def test_decision_execution_service_builder_preserves_runtime_execution_contract(monkeypatch) -> None:
    executor = _Executor()
    service = build_decision_execution_service(executor=executor, keyring='kr')

    import runtime.execution.decision_execution_service as mod

    fake_module = type('M', (), {'DecisionCommand': _DecisionCommand})
    monkeypatch.setattr(mod.importlib, 'import_module', lambda name: fake_module)

    result = service.run(_DecisionCommand())
    assert result['status'] == 'ok'
    assert executor.last == {'signed_with': 'kr', 'validated': True}
