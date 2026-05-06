from __future__ import annotations

import pytest
from fastapi import HTTPException

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.rate_limit_dependencies import RateLimitDependencyBundle
from entrypoints.api.request_context import RequestContext
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _quota_bundle(tenant_id: str, limit: float) -> TenantPolicyBundle:
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


def test_rate_limit_dependency_consumes_quota_for_principal_tenant() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_quota_bundle('tenant-a', 1))
    bundle = RateLimitDependencyBundle(tenant_quota_guard=TenantQuotaGuard(policy_store=store))
    principal = AuthPrincipal(subject='svc', tenant_id='tenant-a')
    request_context = RequestContext(tenant_id='tenant-a')

    bundle.require_quota(principal=principal, request_context=request_context, dimension='actions_per_hour')

    with pytest.raises(HTTPException) as exc:
        bundle.require_quota(principal=principal, request_context=request_context, dimension='actions_per_hour')

    assert exc.value.status_code == 429
    assert exc.value.detail['reason'] == 'quota exceeded'
    assert exc.value.headers['Retry-After'] == '3600'


def test_rate_limit_dependency_uses_request_context_when_principal_has_no_tenant() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_quota_bundle('tenant-a', 1))
    bundle = RateLimitDependencyBundle(tenant_quota_guard=TenantQuotaGuard(policy_store=store))

    bundle.require_quota(
        principal=AuthPrincipal(subject='user', tenant_id=None),
        request_context=RequestContext(tenant_id='tenant-a'),
        dimension='actions_per_hour',
    )

    with pytest.raises(HTTPException):
        bundle.require_quota(
            principal=AuthPrincipal(subject='user', tenant_id=None),
            request_context=RequestContext(tenant_id='tenant-a'),
            dimension='actions_per_hour',
        )


def test_rate_limit_dependency_rejects_blank_dimension() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_quota_bundle('tenant-a', 1))
    bundle = RateLimitDependencyBundle(tenant_quota_guard=TenantQuotaGuard(policy_store=store))

    with pytest.raises(ValueError, match='dimension is required'):
        bundle.require_quota(
            principal=AuthPrincipal(subject='svc', tenant_id='tenant-a'),
            request_context=RequestContext(tenant_id='tenant-a'),
            dimension='   ',
        )
