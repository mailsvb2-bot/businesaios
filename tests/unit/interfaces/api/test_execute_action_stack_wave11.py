from __future__ import annotations

from dataclasses import dataclass, field
import threading

from interfaces.api.action_models import ExecuteActionRequest
from interfaces.api.execute_action_api_stack import build_execute_action_api_stack
from interfaces.api.execute_action_with_guards import ExecuteActionWithGuards
from entrypoints.api.request_context import RequestContext
from interfaces.api.route_handlers import RouteHandlers
from observability.action_audit_log import ActionAuditLog
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_runtime_limits import TenantRuntimeLimits
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope


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
    assert quota_guard.snapshot(tenant_id='tenant-a')['actions_per_hour'] == 1.0
    latest = audit_log.latest_by_action(action_id='a-1')
    assert latest is not None
    assert latest['payload']['stage'] == 'control_plane.executed'

from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore


def test_build_execute_action_api_stack_replays_across_process_like_rebuilds_with_durable_store(tmp_path) -> None:
    service = _Service()
    durable_store = SQLiteIdempotencyStore(tmp_path / 'api-idempotency.sqlite3')
    request = ExecuteActionRequest(
        action_type='launch',
        payload={'tenant_id': 'tenant-a', 'idempotency_key': 'idem-1', 'action_id': 'a-1'},
    )

    stack_a = build_execute_action_api_stack(
        application_service=service,
        idempotency_store=durable_store,
    )
    first = stack_a.handle(request, request_context=RequestContext(tenant_id='tenant-a'))

    stack_b = build_execute_action_api_stack(
        application_service=service,
        idempotency_store=durable_store,
    )
    second = stack_b.handle(request, request_context=RequestContext(tenant_id='tenant-a'))

    assert first.status == 'ok'
    assert second.status == 'ok'
    assert service.calls == 1


def test_route_handlers_thread_explicit_identity_into_canonical_execute_action_port() -> None:
    class _IdentityPort:
        def __init__(self) -> None:
            self.last_request_context = None
            self.last_idempotency_key = None
            self.last_action_id = None

        def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None):
            self.last_request_context = request_context
            self.last_idempotency_key = idempotency_key
            self.last_action_id = action_id
            return type('R', (), {
                'status': 'ok',
                'action_type': request.action_type,
                'reason': 'delegated',
                'details': {},
                'capability_view': {},
            })()

    port = _IdentityPort()
    handlers = RouteHandlers(application_service=_Service(), execute_action_port=port)
    context = RequestContext(tenant_id='tenant-a')

    handlers.execute_action(
        ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-42',
        action_id='action-42',
    )

    assert port.last_request_context is context
    assert port.last_idempotency_key == 'idem-42'
    assert port.last_action_id == 'action-42'



def test_request_context_generated_ids_are_stable_across_repeated_calls() -> None:
    context = RequestContext()

    first_request_id = context.normalized_request_id()
    second_request_id = context.normalized_request_id()
    first_correlation_id = context.normalized_correlation_id()
    second_correlation_id = context.normalized_correlation_id()
    redacted = context.redacted_dict()

    assert first_request_id == second_request_id
    assert first_correlation_id == second_correlation_id
    assert first_request_id == first_correlation_id
    assert redacted['request_id']
    assert redacted['correlation_id']


def test_execute_action_stack_audit_keeps_generated_request_identity_stable_without_headers() -> None:
    service = _Service()
    audit_log = ActionAuditLog()
    stack = build_execute_action_api_stack(
        application_service=service,
        action_audit_log=audit_log,
    )
    context = RequestContext(tenant_id='tenant-a')

    response = stack.handle(
        ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a', 'action_id': 'a-stable'}),
        request_context=context,
    )

    assert response.status == 'ok'
    records = [record for record in audit_log.records if record.get('action_id') == 'a-stable']
    assert len(records) >= 3
    request_ids = {record['payload']['request_context']['request_id'] for record in records}
    correlation_ids = {record['payload']['request_context']['correlation_id'] for record in records}
    trace_ids = {record.get('trace_id') for record in records}
    assert len(request_ids) == 1
    assert len(correlation_ids) == 1
    assert len(trace_ids) == 1


def test_route_handlers_fallback_threads_identity_into_execute_action_handler() -> None:
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
                'reason': 'handled',
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
            assert self.release.wait(2.0)
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
    assert service.started.wait(1.0)

    second = stack_b.handle(request, request_context=context)
    service.release.set()
    thread.join(timeout=2.0)

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

    service = _FailingService()
    stack = build_execute_action_api_stack(application_service=service)
    request = ExecuteActionRequest(action_type='email.send', payload={'recipient': 'ops@example.com'})
    context = RequestContext(tenant_id='tenant-fail', request_id='req-terminal')

    try:
        stack.handle(request, request_context=context, idempotency_key='idem-terminal')
    except RuntimeError as exc:
        assert str(exc) == 'boom'
    else:
        raise AssertionError('expected initial failure')

    calls_after_failure = service.calls
    assert calls_after_failure >= 1

    second = stack.handle(request, request_context=context, idempotency_key='idem-terminal')

    assert second.status == 'blocked'
    assert second.reason == 'idempotency_terminal_failed'
    assert service.calls == calls_after_failure



def test_execute_action_audit_payload_redacts_request_secrets() -> None:
    audit_log = ActionAuditLog()
    stack = build_execute_action_api_stack(application_service=_Service(), action_audit_log=audit_log)

    response = stack.handle(
        ExecuteActionRequest(
            action_type='launch',
            payload={'tenant_id': 'tenant-a', 'action_id': 'a-secret', 'api_key': 'super-secret', 'access_token': 'abc123'},
        ),
        request_context=RequestContext(tenant_id='tenant-a'),
    )

    assert response.status == 'ok'
    latest = audit_log.latest_by_action(action_id='a-secret')
    assert latest is not None
    payload = latest['payload']['request_payload']
    assert payload['api_key'] == '***REDACTED***'
    assert payload['access_token'] == '***REDACTED***'
