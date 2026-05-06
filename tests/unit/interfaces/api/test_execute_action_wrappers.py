from __future__ import annotations

import threading

import pytest

from infra.feature_flag_store import InMemoryFeatureFlagStore
from infra.feature_flags import FeatureFlags
from infra.idempotency import IdempotencyExecutor
from infra.idempotency_store import InMemoryIdempotencyStore
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.retry_models import RetryPolicySpec
from infra.retry_policy import RetryPolicy
from infra.runtime_guardrails import RuntimeGuardrails
from interfaces.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from interfaces.api.execute_action_with_control_plane import ExecuteActionWithControlPlane
from interfaces.api.execute_action_with_guards import ExecuteActionWithGuards
from entrypoints.api.request_context import RequestContext
from observability.action_audit_log import ActionAuditLog
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


class _OkHandler:
    def __init__(self) -> None:
        self.calls = 0

    def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
        self.calls += 1
        return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='done')


class _FlakyHandler:
    def __init__(self) -> None:
        self.calls = 0

    def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError('boom')
        return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='retried')



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

def _guardrails() -> RuntimeGuardrails:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    flags.enable('api.execute_action.enabled')
    return RuntimeGuardrails(
        feature_flags=flags,
        kill_switches=KillSwitchRegistry(),
        maintenance_mode=MaintenanceMode(),
    )


def test_execute_action_with_control_plane_blocks_when_guardrails_fail() -> None:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    wrapper = ExecuteActionWithControlPlane(handler=_OkHandler(), guardrails=RuntimeGuardrails(flags, KillSwitchRegistry(), MaintenanceMode()))

    response = wrapper.handle(request=ExecuteActionRequest(action_type='x', payload={}))

    assert response.status == 'blocked'
    assert 'feature_flag_disabled:api.execute_action.enabled' in str(response.reason)


def test_execute_action_with_control_plane_consumes_quota_after_success_only() -> None:
    handler = _OkHandler()
    store = InMemoryTenantPolicyStore()
    store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 2}))
    quota = TenantQuotaGuard(policy_store=store)
    audit = ActionAuditLog()
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        tenant_quota_guard=quota,
        action_audit_log=audit,
    )

    request = ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a', 'action_id': 'a-1'})
    response = wrapper.handle(request=request, request_context=RequestContext(tenant_id='tenant-a', correlation_id='c-1'))

    assert response.status == 'ok'
    assert handler.calls == 1
    assert quota.snapshot(tenant_id='tenant-a')['actions_per_hour'] == 1.0
    assert audit.latest_by_action(action_id='a-1') is not None


def test_execute_action_with_guards_retries_and_idempotently_reuses_result() -> None:
    handler = _FlakyHandler()
    wrapper = ExecuteActionWithGuards(
        handler=handler,
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=2, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
    )
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'k-1', 'action_id': 'a-1'})

    first = wrapper.handle(request=request)
    second = wrapper.handle(request=request)

    assert first.status == 'ok'
    assert second.status == 'ok'
    assert handler.calls == 2


def test_execute_action_with_guards_requires_idempotency_key_fail_closed() -> None:
    wrapper = ExecuteActionWithGuards(
        handler=_OkHandler(),
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
    )

    with pytest.raises(ValueError):
        wrapper.handle(request=ExecuteActionRequest(action_type='launch', payload={}))


def test_execute_action_with_control_plane_blocked_response_uses_canonical_presenter_shape() -> None:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    wrapper = ExecuteActionWithControlPlane(handler=_OkHandler(), guardrails=RuntimeGuardrails(flags, KillSwitchRegistry(), MaintenanceMode()))

    response = wrapper.handle(request=ExecuteActionRequest(action_type='x', payload={}))

    assert response.status == 'blocked'
    assert response.details['control_plane_stage'] == 'guardrails_blocked'
    assert response.details['guardrail_reasons']
    assert response.capability_view == {}


def test_execute_action_with_control_plane_quota_blocked_response_preserves_details() -> None:
    handler = _OkHandler()
    store = InMemoryTenantPolicyStore()
    store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 0}))
    quota = TenantQuotaGuard(policy_store=store)
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        tenant_quota_guard=quota,
    )

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={'tenant_id': 'tenant-a'}),
        request_context=RequestContext(tenant_id='tenant-a'),
    )

    assert response.status == 'blocked'
    assert response.details['control_plane_stage'] == 'quota_blocked'
    assert response.details['quota_dimension'] == 'actions_per_hour'
    assert handler.calls == 0


def test_execute_action_with_control_plane_threads_identity_to_handler_when_supported() -> None:
    class _IdentityHandler:
        def __init__(self) -> None:
            self.calls = 0
            self.request_context = None
            self.idempotency_key = None
            self.action_id = None

        def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None):
            self.calls += 1
            self.request_context = request_context
            self.idempotency_key = idempotency_key
            self.action_id = action_id
            return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='done')

    handler = _IdentityHandler()
    wrapper = ExecuteActionWithControlPlane(handler=handler, guardrails=_guardrails())
    context = RequestContext(tenant_id='tenant-a', correlation_id='c-1')

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-1',
        action_id='action-1',
    )

    assert response.status == 'ok'
    assert handler.calls == 1
    assert handler.request_context is context
    assert handler.idempotency_key == 'idem-1'
    assert handler.action_id == 'action-1'


def test_execute_action_with_guards_scopes_storage_key_by_tenant_for_idempotent_replay() -> None:
    handler = _OkHandler()
    wrapper = ExecuteActionWithGuards(
        handler=handler,
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
    )
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'k-1'})

    first = wrapper.handle(request=request, request_context=RequestContext(tenant_id='tenant-a'))
    second = wrapper.handle(request=request, request_context=RequestContext(tenant_id='tenant-a'))
    third = wrapper.handle(request=request, request_context=RequestContext(tenant_id='tenant-b'))

    assert first.status == 'ok'
    assert second.status == 'ok'
    assert third.status == 'ok'
    assert handler.calls == 2



def test_execute_action_with_guards_threads_identity_to_handler_when_supported() -> None:
    class _IdentityHandler:
        def __init__(self) -> None:
            self.calls = 0
            self.request_context = None
            self.idempotency_key = None
            self.action_id = None

        def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None):
            self.calls += 1
            self.request_context = request_context
            self.idempotency_key = idempotency_key
            self.action_id = action_id
            return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='done')

    handler = _IdentityHandler()
    wrapper = ExecuteActionWithGuards(
        handler=handler,
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
    )
    context = RequestContext(tenant_id='tenant-a', request_id='req-1')

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-1',
        action_id='action-1',
    )

    assert response.status == 'ok'
    assert handler.calls == 1
    assert handler.request_context is context
    assert handler.idempotency_key == 'idem-1'
    assert handler.action_id == 'action-1'



def test_execute_action_with_guards_audit_truthfully_marks_replay_and_uses_normalized_trace_id() -> None:
    audit = ActionAuditLog()
    handler = _OkHandler()
    wrapper = ExecuteActionWithGuards(
        handler=handler,
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
        action_audit_log=audit,
    )
    context = RequestContext(request_id='req-42', tenant_id='tenant-a')
    request = ExecuteActionRequest(action_type='launch', payload={'action_id': 'a-42'})

    first = wrapper.handle(request=request, request_context=context, idempotency_key='idem-42')
    second = wrapper.handle(request=request, request_context=context, idempotency_key='idem-42')

    assert first.status == 'ok'
    assert second.status == 'ok'
    guard_records = [
        item for item in audit.records
        if item.get('action_id') == 'a-42' and str(item.get('payload', {}).get('stage', '')).startswith('guards.')
    ]
    assert guard_records[-1]['trace_id'] == 'req-42'
    assert guard_records[-1]['payload']['idempotency_resolution'] == 'replay_completed'
    assert guard_records[-1]['payload']['replayed'] is True
    assert guard_records[-1]['payload']['request_context']['request_id'] == 'req-42'



def test_execute_action_with_control_plane_audit_payload_includes_request_context_snapshot() -> None:
    handler = _OkHandler()
    audit = ActionAuditLog()
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        action_audit_log=audit,
    )
    context = RequestContext(tenant_id='tenant-a', request_id='req-7', correlation_id='corr-7', actor_id='user-7')

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={'action_id': 'a-7'}),
        request_context=context,
    )

    assert response.status == 'ok'
    latest = audit.latest_by_action(action_id='a-7')
    assert latest is not None
    assert latest['payload']['request_context']['request_id'] == 'req-7'
    assert latest['payload']['request_context']['correlation_id'] == 'corr-7'
    assert latest['payload']['request_context']['tenant_id'] == 'tenant-a'


def test_execute_action_with_control_plane_bypasses_quota_for_known_replay() -> None:
    class _ReplayAwareHandler:
        def __init__(self) -> None:
            self.calls = 0

        def has_completed_response(self, *, request, request_context=None, idempotency_key=None):
            return True

        def handle(self, request, *, request_context=None, idempotency_key=None, action_id=None):
            self.calls += 1
            return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='replayed')

    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 0}))
    quota_guard = TenantQuotaGuard(policy_store=policy_store)
    audit = ActionAuditLog()
    handler = _ReplayAwareHandler()
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        tenant_quota_guard=quota_guard,
        action_audit_log=audit,
    )

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={'action_id': 'replay-1'}),
        request_context=RequestContext(tenant_id='tenant-a'),
        idempotency_key='idem-replay-1',
    )

    assert response.status == 'ok'
    assert handler.calls == 1
    latest = audit.latest_by_action(action_id='replay-1')
    assert latest is not None
    assert latest['payload']['stage'] == 'control_plane.replayed'
    assert latest['payload']['known_replay'] is True
    assert quota_guard.snapshot(tenant_id='tenant-a')['actions_per_hour'] == 0.0


def test_execute_action_with_control_plane_does_not_consume_quota_twice_on_replay() -> None:
    audit = ActionAuditLog()
    handler = ExecuteActionWithGuards(
        handler=_OkHandler(),
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
        action_audit_log=audit,
    )
    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 5}))
    quota_guard = TenantQuotaGuard(policy_store=policy_store)
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        tenant_quota_guard=quota_guard,
        action_audit_log=audit,
    )
    request = ExecuteActionRequest(action_type='launch', payload={'action_id': 'quota-replay-1'})
    context = RequestContext(tenant_id='tenant-a', request_id='req-quota-replay-1')

    first = wrapper.handle(request=request, request_context=context, idempotency_key='idem-quota-replay-1')
    second = wrapper.handle(request=request, request_context=context, idempotency_key='idem-quota-replay-1')

    assert first.status == 'ok'
    assert second.status == 'ok'
    assert quota_guard.snapshot(tenant_id='tenant-a')['actions_per_hour'] == 1.0
    stages = [
        item['payload']['stage']
        for item in audit.records
        if item.get('action_id') == 'quota-replay-1' and str(item.get('payload', {}).get('stage', '')).startswith('control_plane.')
    ]
    assert 'control_plane.quota_bypassed_replay' in stages
    assert stages[-1] == 'control_plane.replayed'



def test_execute_action_with_guards_blocks_duplicate_in_progress_without_double_execution() -> None:
    class _SlowHandler:
        def __init__(self) -> None:
            self.calls = 0
            self.started = threading.Event()
            self.release = threading.Event()

        def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
            self.calls += 1
            self.started.set()
            assert self.release.wait(2.0)
            return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='done')

    handler = _SlowHandler()
    audit = ActionAuditLog()
    wrapper = ExecuteActionWithGuards(
        handler=handler,
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
        action_audit_log=audit,
    )
    request = ExecuteActionRequest(action_type='launch', payload={'idempotency_key': 'idem-concurrent', 'action_id': 'a-concurrent'})
    first_result: dict[str, object] = {}

    def _run_first() -> None:
        first_result['response'] = wrapper.handle(request=request, request_context=RequestContext(tenant_id='tenant-a'))

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert handler.started.wait(1.0)

    second = wrapper.handle(request=request, request_context=RequestContext(tenant_id='tenant-a'))
    handler.release.set()
    thread.join(timeout=2.0)

    first = first_result['response']
    assert isinstance(first, ExecuteActionResponse)
    assert first.status == 'ok'
    assert second.status == 'blocked'
    assert second.reason == 'idempotency_in_progress'
    assert second.details['guard_stage'] == 'idempotency_in_progress'
    assert handler.calls == 1
    guard_stages = [
        item['payload']['stage']
        for item in audit.records
        if item.get('action_id') == 'a-concurrent' and str(item.get('payload', {}).get('stage', '')).startswith('guards.')
    ]
    assert 'guards.idempotency_in_progress' in guard_stages


def test_execute_action_with_control_plane_bypasses_quota_for_known_in_progress_duplicate() -> None:
    class _SlowHandler:
        def __init__(self) -> None:
            self.calls = 0
            self.started = threading.Event()
            self.release = threading.Event()

        def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
            self.calls += 1
            self.started.set()
            assert self.release.wait(2.0)
            return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='done')

    handler = _SlowHandler()
    audit = ActionAuditLog()
    guarded = ExecuteActionWithGuards(
        handler=handler,
        retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
        idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
        action_audit_log=audit,
    )
    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_tenant_policy_bundle('tenant-a', {'actions_per_hour': 1}))
    quota_guard = TenantQuotaGuard(policy_store=policy_store)
    wrapper = ExecuteActionWithControlPlane(
        handler=guarded,
        guardrails=_guardrails(),
        tenant_quota_guard=quota_guard,
        action_audit_log=audit,
    )
    request = ExecuteActionRequest(action_type='launch', payload={'action_id': 'quota-inflight-1'})
    context = RequestContext(tenant_id='tenant-a', request_id='req-inflight-1')
    first_result: dict[str, object] = {}

    def _run_first() -> None:
        first_result['response'] = wrapper.handle(request=request, request_context=context, idempotency_key='idem-inflight-1')

    thread = threading.Thread(target=_run_first)
    thread.start()
    assert handler.started.wait(1.0)

    second = wrapper.handle(request=request, request_context=context, idempotency_key='idem-inflight-1')
    handler.release.set()
    thread.join(timeout=2.0)

    first = first_result['response']
    assert isinstance(first, ExecuteActionResponse)
    assert first.status == 'ok'
    assert second.status == 'blocked'
    assert second.reason == 'idempotency_in_progress'
    assert quota_guard.snapshot(tenant_id='tenant-a')['actions_per_hour'] == 1.0
    stages = [
        item['payload']['stage']
        for item in audit.records
        if item.get('action_id') == 'quota-inflight-1' and str(item.get('payload', {}).get('stage', '')).startswith('control_plane.')
    ]
    assert 'control_plane.quota_bypassed_in_progress' in stages
    assert 'control_plane.idempotency_in_progress' in stages



def test_execute_action_wrappers_thread_identity_into_kwargs_only_downstream_handler() -> None:
    class _KwargsOnlyHandler:
        def __init__(self) -> None:
            self.calls = []

        def handle(self, **kwargs):
            self.calls.append(dict(kwargs))
            request = kwargs['request']
            return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='done', details={})

    handler = _KwargsOnlyHandler()
    audit = ActionAuditLog()
    wrapper = ExecuteActionWithControlPlane(
        handler=ExecuteActionWithGuards(
            handler=handler,
            retry_policy=RetryPolicy(spec=RetryPolicySpec(max_attempts=1, delay_seconds=0.0)),
            idempotency=IdempotencyExecutor(store=InMemoryIdempotencyStore()),
            action_audit_log=audit,
        ),
        guardrails=_guardrails(),
        action_audit_log=audit,
    )
    context = RequestContext(tenant_id='tenant-a', request_id='req-kwargs-handler')

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-kwargs-handler',
        action_id='action-kwargs-handler',
    )

    assert response.status == 'ok'
    assert handler.calls
    call = handler.calls[-1]
    assert call['request_context'] is context
    assert call['idempotency_key'] == 'idem-kwargs-handler'
    assert call['action_id'] == 'action-kwargs-handler'
