from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from governance.rbac_contract import Permission, RoleId
from entrypoints.api.api_key_policy import ApiKeyPolicy, InMemoryApiKeyStore
from entrypoints.api.auth_contract import RequestAuthentication
from adapters.api.fastapi.auth_dependencies import CompositeAuthPolicy
from entrypoints.api.authz_dependencies import AuthzDependencyBundle
from entrypoints.api.jwt_policy import JwtClaims, JwtPolicy
from entrypoints.api.rate_limit_dependencies import RateLimitDependencyBundle
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from entrypoints.api.tenant_route_guards import TenantRouteGuard
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_contract import TenantPlan, TenantRecord, TenantStatus, utc_now
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import InMemoryTenantRegistry
from tenancy.tenant_runtime_limits import TenantRuntimeLimits
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle


def _security_guard():
    return ApiSecurityOwnerBundle.default(audit_path='runtime/data/security/test_control_plane_auth_guard.jsonl').api_surface_guard


def _bundle(tenant_id: str) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'api_requests_per_hour': 1},
    )


def test_composite_auth_fails_closed_on_ambiguous_mechanisms() -> None:
    store = InMemoryApiKeyStore(pepper='p')
    _, token = store.issue(tenant_id='t1', subject='svc', roles=(RoleId.OWNER,))
    policy = CompositeAuthPolicy(
        api_key_policy=ApiKeyPolicy(store=store),
        jwt_policy=JwtPolicy(secret='secret', audience='control-plane'),
    )

    verdict = policy.authenticate(
        RequestAuthentication(
            tenant_id='t1',
            api_key=token,
            authorization='Bearer some.jwt',
        )
    )
    assert verdict.allowed is False
    assert verdict.reason == 'ambiguous_authentication_mechanisms'


def test_jwt_policy_roundtrip_and_authenticate() -> None:
    policy = JwtPolicy(secret='secret', audience='control-plane')
    token = policy.issue(
        JwtClaims(
            subject='user-1',
            tenant_id='tenant-a',
            audience='control-plane',
            roles=(RoleId.OWNER,),
            expires_at=utc_now() + timedelta(minutes=5),
        )
    )
    verdict = policy.authenticate(RequestAuthentication(tenant_id='tenant-a', authorization=f'Bearer {token}'))
    assert verdict.allowed is True
    assert verdict.principal is not None
    assert verdict.principal.tenant_id == 'tenant-a'


def test_tenant_route_guard_validates_registry_and_activity() -> None:
    registry = InMemoryTenantRegistry(
        records=(
            TenantRecord(tenant_id='tenant-a', display_name='Tenant A', status=TenantStatus.ACTIVE, plan=TenantPlan.ENTERPRISE),
        )
    )
    guard = TenantRouteGuard(tenant_registry=registry, require_active_tenant=True, security_guard=_security_guard())
    tenant_id = guard.enforce(
        principal=AuthPrincipal(subject='s', tenant_id='tenant-a', actor_id='a', roles=(RoleId.OWNER,)),
        request_context=RequestContext(tenant_id='tenant-a'),
        body={'tenant_id': 'tenant-a'},
    )
    assert tenant_id == 'tenant-a'


def test_authz_dependency_uses_resource_context() -> None:
    bundle = AuthzDependencyBundle.default()
    bundle.require(
        principal=AuthPrincipal(subject='s', tenant_id='tenant-a', actor_id='a', roles=(RoleId.OWNER,)),
        request_context=RequestContext(tenant_id='tenant-a'),
        permission=Permission.MANAGE_TENANT_POLICY,
        action_name='api.control-plane.admin.get_tenant_policy',
        resource={'resource_type': 'tenant_policy', 'resource_id': 'tenant-a'},
    )


def test_rate_limit_dependency_returns_429_when_quota_exhausted() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a'))
    deps = RateLimitDependencyBundle(tenant_quota_guard=TenantQuotaGuard(policy_store=store))
    principal = AuthPrincipal(subject='s', tenant_id='tenant-a', actor_id='a', roles=(RoleId.OWNER,))
    request_context = RequestContext(tenant_id='tenant-a')
    deps.require_quota(principal=principal, request_context=request_context, dimension='api_requests_per_hour')
    with pytest.raises(HTTPException) as exc:
        deps.require_quota(principal=principal, request_context=request_context, dimension='api_requests_per_hour')
    assert exc.value.status_code == 429
