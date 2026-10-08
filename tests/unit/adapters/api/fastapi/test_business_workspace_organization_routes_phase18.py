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
