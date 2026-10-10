from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import analytics_routes


class _RequestContext:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.metadata = {}

    def with_metadata(self, **metadata):
        clone = _RequestContext(self.tenant_id)
        clone.metadata = {**self.metadata, **metadata}
        return clone


class _Handlers:
    def __init__(self) -> None:
        self.calls = []

    def get_business_scorecard(self, *, tenant_id: str, window_days: int):
        self.calls.append(("business", tenant_id, window_days))
        return {"tenant_id": tenant_id}

    def get_dashboard_bundle(self, *, tenant_id: str, window_days: int):
        self.calls.append(("dashboard", tenant_id, window_days))
        return {"tenant_id": tenant_id}


class _Guard:
    def __init__(self, *, allowed_tenant: str) -> None:
        self.allowed_tenant = allowed_tenant
        self.calls = []

    def enforce(self, *, route_path, request_context, body, principal):
        self.calls.append((route_path, request_context.tenant_id, dict(body), principal.tenant_id))
        if str(body.get("tenant_id") or "") != self.allowed_tenant:
            raise PermissionError("tenant_scope_mismatch")


def _route(router: APIRouter, path: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and "GET" in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"route not found: {path}")


def _principal(tenant_id: str = "tenant-session"):
    return SimpleNamespace(tenant_id=tenant_id)


def test_analytics_business_route_allows_authenticated_matching_tenant(monkeypatch) -> None:
    router = APIRouter()
    handlers = _Handlers()
    guard = _Guard(allowed_tenant="tenant-session")
    analytics_routes.register_analytics_routes(
        router=router,
        analytics_handlers=handlers,
        security_guard=guard,
        auth_bundle=object(),
    )
    monkeypatch.setattr(
        analytics_routes,
        "authorize_request",
        lambda **_: (_RequestContext("tenant-session"), _principal()),
    )

    result = _route(router, "/analytics/business/{tenant_id}")(
        "tenant-session",
        object(),
        30,
    )

    assert result == {"tenant_id": "tenant-session"}
    assert handlers.calls == [("business", "tenant-session", 30)]
    assert guard.calls == [
        (
            "/analytics/business/{tenant_id}",
            "tenant-session",
            {"tenant_id": "tenant-session"},
            "tenant-session",
        )
    ]


@pytest.mark.parametrize(
    "path,kind",
    [
        ("/analytics/business/{tenant_id}", "business"),
        ("/analytics/dashboard/{tenant_id}", "dashboard"),
    ],
)
def test_analytics_routes_fail_closed_before_handler_for_foreign_tenant(
    monkeypatch,
    path: str,
    kind: str,
) -> None:
    router = APIRouter()
    handlers = _Handlers()
    guard = _Guard(allowed_tenant="tenant-session")
    analytics_routes.register_analytics_routes(
        router=router,
        analytics_handlers=handlers,
        security_guard=guard,
        auth_bundle=object(),
    )
    monkeypatch.setattr(
        analytics_routes,
        "authorize_request",
        lambda **_: (_RequestContext("tenant-session"), _principal()),
    )

    with pytest.raises(HTTPException) as exc:
        _route(router, path)("tenant-attacker", object(), 30)

    assert exc.value.status_code == 403
    assert exc.value.detail == "tenant_scope_mismatch"
    assert handlers.calls == []
    assert guard.calls[0][2] == {"tenant_id": "tenant-attacker"}
