from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

import pytest

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.control_plane_security_guard import ControlPlaneSecurityGuard
from entrypoints.api.request_context import RequestContext
from governance.rbac_contract import RoleId


def _principal() -> AuthPrincipal:
    now = datetime.now(UTC)
    return AuthPrincipal(
        subject='owner-1',
        tenant_id='tenant-a',
        actor_id='owner-1',
        roles=(RoleId.OWNER,),
        metadata={
            'auth_type': 'jwt',
            'issued_at': (now - timedelta(minutes=1)).isoformat(),
            'expires_at': (now + timedelta(minutes=10)).isoformat(),
            'session_created_at': (now - timedelta(minutes=1)).isoformat(),
            'last_seen_at': now.isoformat(),
            'algorithm': 'HS256',
        },
    )


def test_control_plane_security_guard_denies_secret_scope_over_plaintext_transport() -> None:
    guard = ControlPlaneSecurityGuard()
    with pytest.raises(PermissionError) as exc:
        guard.enforce(
            principal=_principal(),
            request_context=RequestContext(tenant_id='tenant-a', metadata={'transport_encrypted': False, 'method': 'POST', 'path': '/control-plane/connectors/crm/secret-scope/dry-run'}),
            action_name='api.control_plane.connectors.secret_scope_dry_run',
            tenant_id='tenant-a',
            resource_id='connector-secret-scope:tenant-a:crm:billing-token',
            body={'secret_name': 'billing-token'},
        )
    assert str(exc.value) == 'encryption_required'


def test_control_plane_security_guard_allows_metrics_read_over_https() -> None:
    guard = ControlPlaneSecurityGuard()
    verdict = guard.enforce(
        principal=_principal(),
        request_context=RequestContext(tenant_id='tenant-a', metadata={'transport_encrypted': True, 'method': 'GET', 'path': '/control-plane/metrics/tenant/tenant-a'}),
        action_name='api.control_plane.metrics.tenant',
        tenant_id='tenant-a',
        resource_id='tenant-metrics:tenant-a',
    )
    assert verdict['allowed'] is True
