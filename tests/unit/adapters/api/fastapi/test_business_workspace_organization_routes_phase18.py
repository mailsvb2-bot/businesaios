from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_organization_routes as routes


@dataclass
class _Organization:
    organization_id: str
    tenant_id: str
    business_id: str
    name: str


class _Request:
    def __init__(self, key: str = "create-once") -> None:
        self.headers = {"x-idempotency-key": key}


def _endpoint(router: APIRouter, path: str, method: str):
    return next(route.endpoint for route in router.routes if route.path == path and method in route.methods)


def test_organization_create_list_retry_and_business_isolation(monkeypatch) -> None:
    created = {}

    class _Registry:
        def __init__(self, **kwargs):
            pass

        def create(self, **kwargs):
            scope = (kwargs["tenant_id"], kwargs["business_id"], kwargs["organization_id"])
            current = created.get(scope)
            if current is not None and current.name != kwargs["name"]:
                raise ValueError("organization already exists with different identity metadata")
            item = current or _Organization(
                organization_id=kwargs["organization_id"], tenant_id=kwargs["tenant_id"],
                business_id=kwargs["business_id"], name=kwargs["name"],
            )
            created[scope] = item
            return item

    class _Projector:
        def __init__(self, event_store):
            pass

        def list_for_business(self, *, tenant_id, business_id):
            return tuple(v for k, v in created.items() if k[:2] == (tenant_id, business_id))

    actor = {"tenant": "tenant-one", "business": "business-one", "allowed": True}

    def scope(**kwargs):
        if not actor["allowed"]:
            raise HTTPException(status_code=403, detail="owner_business_scope_required")
        assert kwargs["required_scope"] == "provider_control_plane"
        return object(), actor["tenant"], actor["business"]

    async def body(request):
        return {"name": "Clinic"}

    monkeypatch.setattr(routes, "OrganizationRegistry", _Registry)
    monkeypatch.setattr(routes, "OrganizationProjector", _Projector)
    monkeypatch.setattr(routes, "business_owner_scope", scope)
    monkeypatch.setattr(routes, "json_body", body)
    router = APIRouter()
    routes.register_business_workspace_organization_routes(
        router=router, auth_bundle=object(), event_store=object(), idempotency_store=object(),
    )
    create = _endpoint(router, "/business-workspace/organizations", "POST")
    listing = _endpoint(router, "/business-workspace/organizations", "GET")
    first = asyncio.run(create(_Request()))
    retry = asyncio.run(create(_Request()))
    assert retry == first
    assert len(asyncio.run(listing(_Request()))["organizations"]) == 1
    actor["business"] = "business-two"
    assert asyncio.run(listing(_Request()))["organizations"] == []
    other = asyncio.run(create(_Request()))
    assert other["organization"]["organization_id"] != first["organization"]["organization_id"]
    actor["allowed"] = False
    with pytest.raises(HTTPException) as exc:
        asyncio.run(listing(_Request()))
    assert exc.value.status_code == 403


def test_organization_create_requires_idempotency_and_rejects_replay_changes(monkeypatch) -> None:
    class _Registry:
        def __init__(self, **kwargs):
            self.current = None

        def create(self, **kwargs):
            raise ValueError("organization already exists with different identity metadata")

    monkeypatch.setattr(routes, "OrganizationRegistry", _Registry)
    monkeypatch.setattr(routes, "OrganizationProjector", lambda _: object())
    monkeypatch.setattr(
        routes, "business_owner_scope",
        lambda **_: (object(), "tenant", "business"),
    )
    monkeypatch.setattr(routes, "json_body", lambda request: _body())
    router = APIRouter()
    routes.register_business_workspace_organization_routes(
        router=router, auth_bundle=object(), event_store=object(), idempotency_store=object(),
    )
    create = _endpoint(router, "/business-workspace/organizations", "POST")
    with pytest.raises(HTTPException) as error:
        asyncio.run(create(_Request(key="")))
    assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        asyncio.run(create(_Request()))
    assert error.value.status_code == 409


async def _body():
    return {"name": "Clinic"}


def test_organization_http_boundary_uses_real_event_writer_and_survives_reopen(monkeypatch) -> None:
    from reliability.idempotency_store import InMemoryIdempotencyStore
    class MemoryEventStore:
        def __init__(self):
            self.events = []

        def append_event(self, event):
            self.events.append(dict(event))

        def iter_events(self, *, tenant_id, start_ms, end_ms=None, user_id=None, event_type=None):
            for event in self.events:
                if event.get("tenant_id") != tenant_id:
                    continue
                if int(event.get("timestamp_ms") or 0) < start_ms:
                    continue
                if event_type is not None and event.get("event_type") != event_type:
                    continue
                yield dict(event)

    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    actor = {"tenant": "tenant-real", "business": "business-real"}

    def scope(**kwargs):
        assert kwargs["required_scope"] == "provider_control_plane"
        return object(), actor["tenant"], actor["business"]

    async def body(_request):
        return {"name": "Real Clinic", "organization_type": "clinic"}

    monkeypatch.setattr(routes, "business_owner_scope", scope)
    monkeypatch.setattr(routes, "json_body", body)
    first_router = APIRouter()
    routes.register_business_workspace_organization_routes(
        router=first_router, auth_bundle=object(), event_store=events, idempotency_store=claims,
    )
    create = _endpoint(first_router, "/business-workspace/organizations", "POST")
    created = asyncio.run(create(_Request(key="durable-create")))
    assert created["organization"]["name"] == "Real Clinic"
    assert len(events.events) == 1
    assert asyncio.run(create(_Request(key="durable-create"))) == created
    assert len(events.events) == 1

    reopened_router = APIRouter()
    routes.register_business_workspace_organization_routes(
        router=reopened_router, auth_bundle=object(), event_store=events, idempotency_store=claims,
    )
    listing = _endpoint(reopened_router, "/business-workspace/organizations", "GET")
    items = asyncio.run(listing(_Request()))["organizations"]
    assert len(items) == 1
    assert items[0]["organization_id"] == created["organization"]["organization_id"]
    actor["business"] = "another-business"
    assert asyncio.run(listing(_Request()))["organizations"] == []
    actor["tenant"] = "another-tenant"
    actor["business"] = "business-real"
    assert asyncio.run(listing(_Request()))["organizations"] == []
