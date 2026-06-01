from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.authz_dependencies import AuthzDependencyBundle
from entrypoints.api.rbac_route_guards import RoutePermissionGuard
from entrypoints.api.request_context import RequestContext
from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import Permission, RoleId
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from infra.feature_flag_store import InMemoryFeatureFlagStore
from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.runtime_guardrails import RuntimeGuardrails
from interfaces.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from interfaces.api.execute_action_with_control_plane import ExecuteActionWithControlPlane
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
class _Handler:
    calls: int = 0

    def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
        self.calls += 1
        return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='executed')


def _guardrails(enabled: bool = True) -> RuntimeGuardrails:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    if enabled:
        flags.enable('api.execute_action.enabled')
    return RuntimeGuardrails(feature_flags=flags, kill_switches=KillSwitchRegistry(), maintenance_mode=MaintenanceMode())


def _policy_bundle(tenant_id: str) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, require_explicit_allowlist=False),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'actions_per_hour': 2},
    )


def test_enterprise_governed_execution_requires_permission_then_records_audit() -> None:
    authz = AuthzDependencyBundle(rbac_policy=RbacPolicy(role_catalog=RoleCatalog(), permission_matrix=PermissionMatrix()))
    guard = RoutePermissionGuard(permission=Permission.EXECUTE_GENERIC_EXECUTION, action_name='enterprise.execute', action_category='execution')
    principal = AuthPrincipal(subject='owner', tenant_id='tenant-a', actor_id='owner', roles=(RoleId.OWNER,))
    guard.enforce(principal=principal, request_context=RequestContext(tenant_id='tenant-a'), authz=authz)

    store = InMemoryTenantPolicyStore()
    store.save(_policy_bundle('tenant-a'))
    audit = ActionAuditLog()
    wrapper = ExecuteActionWithControlPlane(
        handler=_Handler(),
        guardrails=_guardrails(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=store),
        action_audit_log=audit,
    )

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch_campaign', payload={'tenant_id': 'tenant-a', 'action_id': 'a-1'}),
        request_context=RequestContext(tenant_id='tenant-a', correlation_id='trace-1', request_id='req-1'),
    )

    assert response.status == 'ok'
    stages = [record['payload']['stage'] for record in audit.records if record['action_id'] == 'a-1']
    assert stages == ['control_plane.received', 'control_plane.quota_consumed', 'control_plane.executed']


def test_enterprise_governed_execution_fails_closed_for_unauthorized_principal() -> None:
    authz = AuthzDependencyBundle(rbac_policy=RbacPolicy(role_catalog=RoleCatalog(), permission_matrix=PermissionMatrix()))
    guard = RoutePermissionGuard(permission=Permission.EXECUTE_GENERIC_EXECUTION, action_name='enterprise.execute', action_category='execution')
    principal = AuthPrincipal(subject='viewer', tenant_id='tenant-a', actor_id='viewer', roles=(RoleId.VIEWER,))

    with pytest.raises(HTTPException) as exc:
        guard.enforce(principal=principal, request_context=RequestContext(tenant_id='tenant-a'), authz=authz)

    assert exc.value.status_code == 403


def test_enterprise_governed_execution_blocks_when_feature_flag_disabled_before_handler() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_policy_bundle('tenant-a'))
    handler = _Handler()
    audit = ActionAuditLog()
    wrapper = ExecuteActionWithControlPlane(
        handler=handler,
        guardrails=_guardrails(enabled=False),
        tenant_quota_guard=TenantQuotaGuard(policy_store=store),
        action_audit_log=audit,
    )

    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='launch_campaign', payload={'tenant_id': 'tenant-a', 'action_id': 'a-blocked'}),
        request_context=RequestContext(tenant_id='tenant-a', correlation_id='trace-blocked', request_id='req-blocked'),
    )

    assert response.status == 'blocked'
    assert handler.calls == 0
    assert audit.latest_by_action(action_id='a-blocked')['payload']['stage'] == 'control_plane.guardrails_blocked'
