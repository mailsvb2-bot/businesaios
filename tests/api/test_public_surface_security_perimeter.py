from __future__ import annotations

import pytest

from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext


class AllowingAdapter:
    def evaluate_surface(self, **_kwargs):
        return {"allowed": True, "reason": "allowed"}


def _guard() -> PublicSurfaceSecurityGuard:
    return PublicSurfaceSecurityGuard(adapter=AllowingAdapter())


def _context(**metadata):
    return RequestContext(
        request_id="req-1",
        tenant_id="tenant-a",
        actor_id="operator-a",
        ip_address="127.0.0.1",
        user_agent="testclient",
        metadata={"transport_encrypted": True, **metadata},
    )


def test_internal_write_requires_external_perimeter_proof() -> None:
    with pytest.raises(PermissionError, match="api_perimeter_auth_required"):
        _guard().enforce(
            route_path="/actions/execute",
            request_context=_context(),
            body={"tenant_id": "tenant-a", "idempotency_key": "idem-1", "action_type": "noop@v1"},
        )


def test_internal_write_requires_tenant_isolation() -> None:
    with pytest.raises(PermissionError, match="api_tenant_isolation_violation"):
        _guard().enforce(
            route_path="/actions/execute",
            request_context=_context(jwt_verified=True),
            body={"tenant_id": "tenant-b", "idempotency_key": "idem-1", "action_type": "noop@v1"},
        )


def test_internal_write_requires_replay_marker() -> None:
    context = RequestContext(
        tenant_id="tenant-a",
        actor_id="operator-a",
        ip_address="127.0.0.1",
        user_agent="testclient",
        metadata={"transport_encrypted": True, "jwt_verified": True},
    )
    with pytest.raises(PermissionError, match="api_replay_protection_required"):
        _guard().enforce(
            route_path="/actions/execute",
            request_context=context,
            body={"tenant_id": "tenant-a", "action_type": "noop@v1"},
        )


def test_internal_write_passes_with_perimeter_tenant_and_replay_marker() -> None:
    verdict = _guard().enforce(
        route_path="/actions/execute",
        request_context=_context(jwt_verified=True),
        body={"tenant_id": "tenant-a", "idempotency_key": "idem-1", "action_type": "noop@v1"},
    )

    assert verdict["allowed"] is True


def test_public_cta_write_keeps_public_entry_open() -> None:
    verdict = _guard().enforce(
        route_path="/public-site/cta/start",
        request_context=RequestContext(
            request_id="public-req-1",
            ip_address="127.0.0.1",
            user_agent="testclient",
            metadata={"transport_encrypted": True},
        ),
        body={"intake": "demo"},
    )

    assert verdict["allowed"] is True
