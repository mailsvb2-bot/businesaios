from __future__ import annotations

from dataclasses import dataclass

from infra.feature_flag_store import InMemoryFeatureFlagStore
from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.runtime_guardrails import RuntimeGuardrails
from interfaces.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from interfaces.api.execute_action_with_control_plane import ExecuteActionWithControlPlane
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


@dataclass
class _AutonomyHandler:
    calls: list[str]

    def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
        self.calls.append(str(request.payload['tenant_id']))
        return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='tick')


def _guardrails() -> RuntimeGuardrails:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    flags.enable('api.execute_action.enabled')
    return RuntimeGuardrails(feature_flags=flags, kill_switches=KillSwitchRegistry(), maintenance_mode=MaintenanceMode())


def _bundle(tenant_id: str, limit: float) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, require_explicit_allowlist=False),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'actions_per_hour': limit},
    )


def test_tenant_isolated_autonomy_loop_keeps_quota_and_audit_separate() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', 1))
    store.save(_bundle('tenant-b', 2))
    audit = ActionAuditLog()
    handler = _AutonomyHandler(calls=[])
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=store),
        action_audit_log=audit,
    )

    first_a = wrapper.handle(request=ExecuteActionRequest(action_type='autonomy_tick', payload={'tenant_id': 'tenant-a', 'action_id': 'a-1'}), request_context=RequestContext(tenant_id='tenant-a', correlation_id='trace-a'))
    blocked_a = wrapper.handle(request=ExecuteActionRequest(action_type='autonomy_tick', payload={'tenant_id': 'tenant-a', 'action_id': 'a-2'}), request_context=RequestContext(tenant_id='tenant-a', correlation_id='trace-a2'))
    first_b = wrapper.handle(request=ExecuteActionRequest(action_type='autonomy_tick', payload={'tenant_id': 'tenant-b', 'action_id': 'b-1'}), request_context=RequestContext(tenant_id='tenant-b', correlation_id='trace-b'))

    assert first_a.status == 'ok'
    assert blocked_a.status == 'blocked'
    assert first_b.status == 'ok'
    assert handler.calls == ['tenant-a', 'tenant-b']
    assert audit.latest_by_action(action_id='a-2')['tenant_id'] == 'tenant-a'
    assert audit.latest_by_action(action_id='b-1')['tenant_id'] == 'tenant-b'


def test_tenant_isolated_autonomy_loop_uses_request_context_tenant_over_payload_tenant() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', 1))
    store.save(_bundle('tenant-b', 1))
    audit = ActionAuditLog()
    handler = _AutonomyHandler(calls=[])
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=store),
        action_audit_log=audit,
    )

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='autonomy_tick', payload={'tenant_id': 'tenant-b', 'action_id': 'tenant-context-wins'}),
        request_context=RequestContext(tenant_id='tenant-a', correlation_id='trace-ctx-wins'),
    )

    assert response.status == 'ok'
    assert audit.latest_by_action(action_id='tenant-context-wins')['tenant_id'] == 'tenant-a'
