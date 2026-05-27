from __future__ import annotations

import threading
from dataclasses import dataclass, field

from entrypoints.api.request_context import RequestContext
from interfaces.api.action_models import ExecuteActionRequest
from interfaces.api.execute_action_api_stack import build_execute_action_api_stack
from interfaces.api.execute_action_with_guards import ExecuteActionWithGuards
from interfaces.api.route_handlers import RouteHandlers
from observability.action_audit_log import ActionAuditLog
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


class _Service:
    def __init__(self) -> None:
        self.calls = 0
        self.last_action = None

    def execute_action(self, action):
        self.calls += 1
        self.last_action = action
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'echo': dict(action.payload)},
        }

    def startup_audit_events(self):
        return ()


class _Port:
    def __init__(self) -> None:
        self.last_request_context = None

    def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None):
        self.last_request_context = request_context
        return type('R', (), {
            'status': 'ok',
            'action_type': request.action_type,
            'reason': 'delegated',
            'details': {},
            'capability_view': {},
        })()



def _tenant_policy_bundle(tenant_id: str, quotas: dict[str, float]) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, require_explicit_allowlist=False),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas=quotas,
    )


def test_execute_action_with_guards_uses_normalized_request_id_when_request_context_has_no_ids() -> None:
    class _OkHandler:
        def handle(self, request):
            return type('R', (), {'status': 'ok', 'action_type': request.action_type, 'reason': 'done'})()

    wrapper = ExecuteActionWithGuards(
        handler=_OkHandler(),
        retry_policy=__import__('infra.retry_policy', fromlist=['RetryPolicy']).RetryPolicy(
            spec=__import__('infra.retry_models', fromlist=['RetryPolicySpec']).RetryPolicySpec(max_attempts=1, delay_seconds=0.0)
        ),
        idempotency=__import__('infra.idempotency', fromlist=['IdempotencyExecutor']).IdempotencyExecutor(
            store=__import__('infra.idempotency_store', fromlist=['InMemoryIdempotencyStore']).InMemoryIdempotencyStore()
        ),
    )

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={}),
        request_context=RequestContext(),
    )

    assert response.status == 'ok'


def test_route_handlers_pass_request_context_into_canonical_execute_action_port() -> None:
    port = _Port()
    handlers = RouteHandlers(application_service=_Service(), execute_action_port=port)
    context = RequestContext(tenant_id='tenant-a')

    handlers.execute_action(ExecuteActionRequest(action_type='launch', payload={}), request_context=context)

    assert port.last_request_context is context


def test_build_execute_action_api_stack_executes_through_canonical_wrappers() -> None:
    service = _Service()
    audit_log = ActionAuditLog()
    store = InMemoryTenantPolicyStore()
    store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 2}))
    quota_guard = TenantQuotaGuard(policy_store=store)
    stack = build_execute_action_api_stack(
        application_service=service,
        tenant_quota_guard=quota_guard,
        action_audit_log=audit_log,
    )

    response = stack.handle(
        ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a', 'action_id': 'a-1'}),
        request_context=RequestContext(tenant_id='tenant-a'),
    )

    assert response.status == 'ok'
    assert service.calls == 1
    assert audit_log.records


def test_build_execute_action_api_stack_replays_completed_idempotency_response() -> None:
    service = _Service()
    stack = build_execute_action_api_stack(application_service=service)
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-1', 'action_id': 'a-1'})
    context = RequestContext(tenant_id='tenant-a')

    first = stack.handle(request, request_context=context)
    second = stack.handle(request, request_context=context)

    assert first.status == 'ok'
    assert second.status == 'ok'
    assert service.calls == 1


def test_build_execute_action_api_stack_blocks_in_progress_idempotency_key() -> None:
    class _BlockingService(_Service):
        def execute_action(self, action):
            self.calls += 1
            self.last_action = action
            return {
                'status': 'ok',
                'action_type': action.action_type,
                'reason': 'executed',
                'details': {'echo': dict(action.payload)},
            }

    service = _BlockingService()
    store = __import__('infra.idempotency_store', fromlist=['InMemoryIdempotencyStore']).InMemoryIdempotencyStore()
    stack = build_execute_action_api_stack(application_service=service, idempotency_store=store)
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-2', 'action_id': 'a-2'})
    context = RequestContext(tenant_id='tenant-a')

    first = stack.handle(request, request_context=context)
    second = stack.handle(request, request_context=context)

    assert first.status == 'ok'
    assert second.status == 'ok'
    assert service.calls == 1


def test_build_execute_action_api_stack_quota_does_not_charge_idempotency_replay() -> None:
    service = _Service()
    audit_log = ActionAuditLog()
    store = InMemoryTenantPolicyStore()
    store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 1}))
    quota_guard = TenantQuotaGuard(policy_store=store)
    stack = build_execute_action_api_stack(
        application_service=service,
        tenant_quota_guard=quota_guard,
        action_audit_log=audit_log,
    )
    request = ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a', 'idempotency_key': 'idem-3', 'action_id': 'a-3'})
    context = RequestContext(tenant_id='tenant-a')

    first = stack.handle(request, request_context=context)
    replay = stack.handle(request, request_context=context)
    blocked = stack.handle(
        ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a', 'idempotency_key': 'idem-4', 'action_id': 'a-4'}),
        request_context=context,
    )

    assert first.status == 'ok'
    assert replay.status == 'ok'
    assert blocked.status == 'blocked'
    assert service.calls == 1


def test_build_execute_action_api_stack_quota_bypasses_in_progress_duplicate() -> None:
    class _SlowService(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def execute_action(self, action):
            self.calls += 1
            self.last_action = action
            self.started.set()
            assert self.release.wait(10.0)
            return {
                'status': 'ok',
                'action_type': action.action_type,
                'reason': 'executed',
                'details': {'echo': dict(action.payload)},
            }

    service = _SlowService()
    audit_log = ActionAuditLog()
    store = InMemoryTenantPolicyStore()
    store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 1}))
    quota_guard = TenantQuotaGuard(policy_store=store)
    stack = build_execute_action_api_stack(
        application_service=service,
        tenant_quota_guard=quota_guard,
        action_audit_log=audit_log,
    )
    request = ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a', 'idempotency_key': 'idem-slow', 'action_id': 'slow-1'})
    context = RequestContext(tenant_id='tenant-a')
    first_result: dict[str, object] = {}

    def _run_first() -> None:
        first_result['response'] = stack.handle(request, request_context=context)

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert service.started.wait(5.0)

    second = stack.handle(request, request_context=context)
    service.release.set()
    thread.join(timeout=10.0)

    assert getattr(first_result['response'], 'status', None) == 'ok'
    assert second.status == 'blocked'
    assert second.reason == 'idempotency_in_progress'
    assert service.calls == 1


def test_route_handlers_delegate_to_explicit_execute_action_handler_with_context() -> None:
    class _Handler:
        def __init__(self) -> None:
            self.request_context = None
            self.idempotency_key = None
            self.action_id = None

        def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None):
            self.request_context = request_context
            self.idempotency_key = idempotency_key
            self.action_id = action_id
            return type('R', (), {
                'status': 'ok',
                'action_type': request.action_type,
                'reason': 'delegated',
                'details': {},
                'capability_view': {},
            })()

    context = RequestContext(tenant_id='tenant-a')
    handler = _Handler()
    route_handlers = RouteHandlers(application_service=_Service(), execute_action_handler=handler)

    response = route_handlers.execute_action(
        ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-9',
        action_id='action-9',
    )

    assert response.status == 'ok'
    assert handler.request_context is context
    assert handler.idempotency_key == 'idem-9'
    assert handler.action_id == 'action-9'


def test_request_context_with_metadata_preserves_generated_identity() -> None:
    context = RequestContext()
    request_id = context.normalized_request_id()
    correlation_id = context.normalized_correlation_id()

    derived = context.with_metadata(route='/actions/execute')

    assert derived.normalized_request_id() == request_id
    assert derived.normalized_correlation_id() == correlation_id
    redacted = derived.redacted_dict()
    assert redacted['request_id']
    assert redacted['correlation_id']



def test_execute_action_stack_durable_idempotency_blocks_parallel_duplicate_without_second_execution(tmp_path) -> None:
    class _BlockingService(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def execute_action(self, action):
            self.calls += 1
            self.last_action = action
            self.started.set()
            assert self.release.wait(10.0)
            return {
                'status': 'ok',
                'action_type': action.action_type,
                'reason': 'executed',
                'details': {'echo': dict(action.payload)},
            }

    service = _BlockingService()
    durable_store = __import__('reliability.idempotency_sqlite_backend', fromlist=['SQLiteIdempotencyStore']).SQLiteIdempotencyStore(
        tmp_path / 'parallel.sqlite3'
    )
    stack_a = build_execute_action_api_stack(application_service=service, idempotency_store=durable_store)
    stack_b = build_execute_action_api_stack(application_service=service, idempotency_store=durable_store)
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-parallel', 'action_id': 'parallel-1'})
    context = RequestContext(tenant_id='tenant-a')
    first_result: dict[str, object] = {}

    def _run_first() -> None:
        first_result['response'] = stack_a.handle(request, request_context=context)

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert service.started.wait(5.0)

    second = stack_b.handle(request, request_context=context)
    service.release.set()
    thread.join(timeout=10.0)

    first = first_result['response']
    assert getattr(first, 'status', None) == 'ok'
    assert second.status == 'blocked'
    assert second.reason == 'idempotency_in_progress'
    assert service.calls == 1


def test_build_api_execute_action_idempotency_store_adapts_reliability_in_memory_store() -> None:
    from interfaces.api.execute_action_idempotency_store import (
        DurableExecuteActionIdempotencyStore,
        build_api_execute_action_idempotency_store,
    )
    from reliability.idempotency_store import InMemoryIdempotencyStore as ReliabilityInMemoryIdempotencyStore

    adapted = build_api_execute_action_idempotency_store(ReliabilityInMemoryIdempotencyStore())

    assert isinstance(adapted, DurableExecuteActionIdempotencyStore)


def test_execute_action_stack_default_idempotency_blocks_terminal_failed_retries() -> None:
    from interfaces.api.execute_action_api_stack import build_execute_action_api_stack

    class _FailingService:
        def __init__(self) -> None:
            self.calls = 0

        def execute_action(self, action):
            self.calls += 1
            raise RuntimeError('boom')

    stack = build_execute_action_api_stack(application_service=_FailingService())
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-fail', 'action_id': 'fail-1'})
    context = RequestContext(tenant_id='tenant-a')

    try:
        stack.handle(request, request_context=context)
    except RuntimeError:
        pass

    second = stack.handle(request, request_context=context)
    assert second.status == 'blocked'
    assert second.reason == 'idempotency_terminal_failed'
