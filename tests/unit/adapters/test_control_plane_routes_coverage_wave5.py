from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest
from fastapi import APIRouter, HTTPException, status

from adapters.api.fastapi import control_plane_routes


@dataclass
class FakePrincipal:
    subject: str = "subject"
    actor_id: str = "actor"
    tenant_id: str = "tenant-demo"


class FakeRequestContext:
    def normalized_request_id(self) -> str:
        return "request-1"


class FakeRequest:
    headers = {
        "X-Event-Id": "event-1",
        "X-Topic": "topic-1",
        "x-amz-request-id": "aws-1",
    }

    async def body(self) -> bytes:
        return b"{\"ok\": true}"


class FakeRoutePermissionGuard:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def enforce(self, *_args: object, **_kwargs: object) -> None:
        return None


class FakeTenantGuard:
    def enforce(self, **kwargs: object) -> str:
        tenant_id = kwargs.get("tenant_id")
        if tenant_id:
            return str(tenant_id)
        body = kwargs.get("body")
        if isinstance(body, dict) and body.get("tenant_id"):
            return str(body["tenant_id"])
        principal = kwargs.get("principal")
        return str(getattr(principal, "tenant_id", "tenant-demo"))


class FakeRateLimitBundle:
    def require_quota(self, *_args: object, **_kwargs: object) -> None:
        return None


class FakeSecurityGuard:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[dict[str, object]] = []

    def enforce(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(dict(kwargs))
        if self.deny:
            raise PermissionError("denied")
        return {"ok": True}


class FakeHandlerBundle:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __getattr__(self, attr: str):
        def _handler(**kwargs: object) -> dict[str, object]:
            self.calls.append((attr, dict(kwargs)))
            if self.name == "webhook" and attr == "receive":
                return {
                    "accepted": True,
                    "handler_bundle": self.name,
                    "handler": attr,
                    "kwargs": dict(kwargs),
                }
            return {
                "handler_bundle": self.name,
                "handler": attr,
                "kwargs": dict(kwargs),
            }

        return _handler


async def _fake_json_body(_request: object) -> dict[str, object]:
    return {
        "tenant_id": "tenant-demo",
        "subject_type": "change",
        "subject_id": "subject-1",
        "reason": "because",
        "required_role_groups": [],
        "min_distinct_approvers": 1,
        "prohibit_self_approval": True,
        "outcome": "approve",
        "rationale": "ok",
        "layout": {"widgets": []},
        "file_path": "application/module.py",
        "risk_type": "coverage",
        "business_id": "business-1",
        "provider_key": "provider-1",
        "secret_name": "token",
        "mode": "read",
        "secret_kind": "api_key",
        "operation": "sync",
        "event_key": "event-1",
        "body": "payload",
        "requested_by": "actor",
        "probe_mode": "dry_run",
        "activate_runtime": False,
        "secrets": {"token": "secret"},
    }


def _route_kwargs(endpoint: object) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    for name, parameter in inspect.signature(endpoint).parameters.items():
        if name == "request":
            kwargs[name] = FakeRequest()
        elif name == "tenant_id":
            kwargs[name] = "tenant-demo"
        elif name == "business_id":
            kwargs[name] = "business-1"
        elif name == "provider_key":
            kwargs[name] = "provider-1"
        elif name == "connector_id":
            kwargs[name] = "connector-1"
        elif name == "queue_name":
            kwargs[name] = "queue-main"
        elif name == "approval_id":
            kwargs[name] = "approval-1"
        elif name == "file_path":
            kwargs[name] = "application/module.py"
        elif name == "block":
            kwargs[name] = "runtime"
        elif name == "risk_type":
            kwargs[name] = "coverage"
        elif name == "trace_id":
            kwargs[name] = "trace-1"
        elif name == "limit":
            kwargs[name] = 2
        elif name == "window_seconds":
            kwargs[name] = 60
        elif parameter.default is inspect.Parameter.empty:
            kwargs[name] = f"{name}-value"
    return kwargs


def _build_router(monkeypatch: pytest.MonkeyPatch, *, deny_security: bool = False) -> tuple[APIRouter, FakeSecurityGuard]:
    monkeypatch.setattr(
        control_plane_routes,
        "authorize_request",
        lambda **_kwargs: (FakeRequestContext(), FakePrincipal()),
    )
    monkeypatch.setattr(
        control_plane_routes,
        "tenant_if_present",
        lambda **_kwargs: "tenant-demo",
    )
    monkeypatch.setattr(control_plane_routes, "json_body", _fake_json_body)
    monkeypatch.setattr(control_plane_routes, "RoutePermissionGuard", FakeRoutePermissionGuard)
    monkeypatch.setattr(control_plane_routes, "first_role", lambda _principal: "admin")
    monkeypatch.setattr(control_plane_routes, "register_analytics_ops_routes", lambda **_kwargs: None)
    monkeypatch.setattr(control_plane_routes, "register_analytics_signed_export_routes", lambda **_kwargs: None)

    router = APIRouter()
    security_guard = FakeSecurityGuard(deny=deny_security)
    handlers = {
        "audit_handlers": FakeHandlerBundle("audit"),
        "approval_handlers": FakeHandlerBundle("approval"),
        "admin_handlers": FakeHandlerBundle("admin"),
        "connector_admin_handlers": FakeHandlerBundle("connector_admin"),
        "provider_admin_handlers": FakeHandlerBundle("provider_admin"),
        "metrics_handlers": FakeHandlerBundle("metrics"),
        "webhook_handlers": FakeHandlerBundle("webhook"),
        "queue_ops_handlers": FakeHandlerBundle("queue_ops"),
    }

    control_plane_routes.register_control_plane_routes(
        router=router,
        auth_bundle=object(),
        authz_bundle=object(),
        tenant_guard=FakeTenantGuard(),
        rate_limit_bundle=FakeRateLimitBundle(),
        security_guard=security_guard,
        analytics_ops_handlers=None,
        analytics_signed_export_handlers=None,
        **handlers,
    )
    return router, security_guard


@pytest.mark.asyncio
async def test_control_plane_registered_routes_execute_with_fake_bundles(monkeypatch: pytest.MonkeyPatch) -> None:
    router, security_guard = _build_router(monkeypatch)

    routes = [route for route in router.routes if hasattr(route, "endpoint")]
    assert len(routes) >= 30

    executed = 0
    for route in routes:
        endpoint = route.endpoint
        result = endpoint(**_route_kwargs(endpoint))
        if inspect.isawaitable(result):
            result = await result

        assert isinstance(result, dict)
        executed += 1

    assert executed >= 30
    assert security_guard.calls


@pytest.mark.asyncio
async def test_control_plane_security_permission_error_maps_to_http_403(monkeypatch: pytest.MonkeyPatch) -> None:
    router, _security_guard = _build_router(monkeypatch, deny_security=True)
    route = next(route for route in router.routes if getattr(route, "path", "") == "/control-plane/audit/actions")

    with pytest.raises(HTTPException) as exc_info:
        result = route.endpoint(**_route_kwargs(route.endpoint))
        if inspect.isawaitable(result):
            await result

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "denied"
