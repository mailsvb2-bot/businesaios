from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext
from governance.rbac_contract import RoleId
from security.security_integration_adapter import SecurityIntegrationAdapter
from security.session_policy import SessionPolicy
from security.token_policy import TokenPolicy


class _ProjectionCheckingAdapter:
    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None

    def evaluate_surface(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = kwargs
        auth = kwargs['auth_payload']
        session = kwargs['session_payload']
        now = datetime.fromisoformat(str(auth['now']))
        token = TokenPolicy().evaluate(
            issued_at=datetime.fromisoformat(str(auth['issued_at'])),
            expires_at=datetime.fromisoformat(str(auth['expires_at'])),
            now=now,
            scopes=tuple(auth['scopes']),
            subject=str(auth['subject']),
            audience=str(auth['audience']),
            issuer=str(auth['issuer']),
            session_id=auth['session_id'],
            algorithm=str(auth['algorithm']),
            key_id=str(auth['key_id']),
        )
        session_verdict = SessionPolicy().evaluate(
            created_at=datetime.fromisoformat(str(session['created_at'])),
            last_seen_at=datetime.fromisoformat(str(session['last_seen_at'])),
            now=datetime.fromisoformat(str(session['now'])),
        )
        return {'allowed': token.allowed and session_verdict.allowed, 'reason': 'allowed' if token.allowed and session_verdict.allowed else token.reason}


def _context() -> RequestContext:
    return RequestContext(
        tenant_id='tenant-live',
        metadata={
            'transport_encrypted': True,
            'api_key_verified': True,
            'idempotency_key': 'post-deploy-test',
        },
    )


def test_public_execute_action_projects_old_sessionless_service_api_key_at_request_time() -> None:
    created_at = datetime.now(UTC) - timedelta(days=7)
    principal = AuthPrincipal(
        subject='production-control-plane-smoke:tenant-live',
        tenant_id='tenant-live',
        actor_id='production-control-plane-smoke:tenant-live',
        roles=(RoleId.OWNER,),
        scopes=('provider_control_plane',),
        metadata={
            'auth_type': 'api_key',
            'principal_kind': 'service',
            'key_id': 'ak_test',
            'created_at': created_at.isoformat(),
            'issued_at': created_at.isoformat(),
            'session_created_at': created_at.isoformat(),
        },
    )
    adapter = _ProjectionCheckingAdapter()
    guard = PublicSurfaceSecurityGuard(adapter=cast(SecurityIntegrationAdapter, adapter))

    verdict = guard.enforce(
        route_path='/actions/execute',
        request_context=_context(),
        body={'action_type': 'pricing.publish_offer', 'payload': {'offer_id': 'offer-test', 'amount': 199}},
        principal=principal,
    )

    assert verdict['allowed'] is True
    assert adapter.last_call is not None
    auth = adapter.last_call['auth_payload']
    session = adapter.last_call['session_payload']
    now = datetime.fromisoformat(str(auth['now']))
    assert datetime.fromisoformat(str(auth['issued_at'])) == now
    assert datetime.fromisoformat(str(auth['expires_at'])) == now + timedelta(seconds=guard.default_token_ttl_seconds)
    assert datetime.fromisoformat(str(session['created_at'])) == now


def test_public_service_api_key_projection_is_capped_by_record_expiry() -> None:
    record_expires_at = datetime.now(UTC) + timedelta(seconds=120)
    principal = AuthPrincipal(
        subject='service',
        tenant_id='tenant-live',
        actor_id='service',
        roles=(RoleId.OWNER,),
        scopes=('provider_control_plane',),
        metadata={
            'auth_type': 'api_key',
            'principal_kind': 'service',
            'key_id': 'ak_test',
            'expires_at': record_expires_at.isoformat(),
        },
    )
    adapter = _ProjectionCheckingAdapter()
    guard = PublicSurfaceSecurityGuard(adapter=cast(SecurityIntegrationAdapter, adapter))

    verdict = guard.enforce(
        route_path='/actions/execute',
        request_context=_context(),
        body={'action_type': 'pricing.publish_offer', 'payload': {'offer_id': 'offer-test', 'amount': 199}},
        principal=principal,
    )

    assert verdict['allowed'] is True
    assert adapter.last_call is not None
    projected_expiry = datetime.fromisoformat(str(adapter.last_call['auth_payload']['expires_at']))
    assert projected_expiry == record_expires_at
