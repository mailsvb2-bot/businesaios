"""Platform-wide introspection must not be available to a public-site OWNER."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from adapters.api.fastapi.router_support import require_platform_scope
from governance.rbac_contract import RoleId


def _principal(tenant: str, *roles: RoleId):
    return SimpleNamespace(tenant_id=tenant, roles=roles)


def test_owner_cannot_enumerate_platform_tenants(monkeypatch):
    monkeypatch.delenv('API_PLATFORM_OPERATOR_TENANT_IDS', raising=False)
    with pytest.raises(HTTPException) as exc:
        require_platform_scope(_principal('customer-tenant', RoleId.OWNER))
    assert exc.value.status_code == 403


def test_operator_requires_explicit_allowlisted_tenant(monkeypatch):
    monkeypatch.setenv('API_PLATFORM_OPERATOR_TENANT_IDS', 'platform-operator')
    with pytest.raises(HTTPException):
        require_platform_scope(_principal('customer-tenant', RoleId.OPERATOR))
    require_platform_scope(_principal('platform-operator', RoleId.OPERATOR))
    require_platform_scope(_principal('system-tenant', RoleId.SYSTEM))


def test_viewer_and_owner_cannot_escalate_using_allowlist(monkeypatch):
    monkeypatch.setenv('API_PLATFORM_OPERATOR_TENANT_IDS', 'platform-operator')
    for role in (RoleId.VIEWER, RoleId.OWNER):
        with pytest.raises(HTTPException):
            require_platform_scope(_principal('platform-operator', role))
