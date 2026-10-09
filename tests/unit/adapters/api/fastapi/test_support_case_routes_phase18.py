from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_support_case_routes as routes
from application.business_autonomy.support_case_registry import SupportCaseRegistry
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _endpoint(router, path, method):
    return next(row.endpoint for row in router.routes if row.path == path and method in row.methods)


def _fixture(monkeypatch):
    registry = SupportCaseRegistry(event_store=MemoryEventStore(), idempotency_store=InMemoryIdempotencyStore())
    owner = SimpleNamespace(actor_id="owner", subject="owner", roles=(RoleId.OWNER,), scopes=(),
                            tenant_id="tenant-a", metadata={"business_id": "business-a"})
    operator = SimpleNamespace(actor_id="support-1", subject="support-1", roles=(RoleId.SUPPORT,),
                               scopes=("support_case_manage",), tenant_id="tenant-a",
                               metadata={"business_id": "business-a"})
    current = {"principal": operator}
    monkeypatch.setattr(routes, "business_owner_scope",
                        lambda **_: (owner, owner.tenant_id, owner.metadata["business_id"]))
    monkeypatch.setattr(routes, "authorize_request", lambda **_: (object(), current["principal"]))
    request_body = {"category": "technical", "summary": "Cannot connect the provider",
                    "idempotency_key": "owner-create-1"}
    async def body(_):
        return request_body
    monkeypatch.setattr(routes, "json_body", body)
    router = APIRouter()
    routes.register_business_workspace_support_case_routes(router=router, auth_bundle=object(), support_cases=registry)
    return registry, router, current, request_body


def test_authenticated_business_owner_creates_and_tracks_canonical_support_case(monkeypatch):
    registry, router, current, body = _fixture(monkeypatch)
    create = _endpoint(router, "/business-workspace/support-cases", "POST")
    inbox = _endpoint(router, "/business-workspace/support-cases", "GET")
    operator_queue = _endpoint(router, "/platform-support/cases", "GET")
    mutate = _endpoint(router, "/platform-support/cases/{case_id}/{action}", "POST")
    case = asyncio.run(create(object()))
    assert case["tenant_id"] == "tenant-a" and case["business_id"] == "business-a"
    assert case["status"] == "open"
    assert asyncio.run(inbox(object()))["cases"] == [case]
    assert asyncio.run(operator_queue(object()))["cases"] == [case]
    body.clear()
    body.update({"expected_revision": case["revision"], "idempotency_key": "op-claim-1"})
    claimed = asyncio.run(mutate(case["id"], "claim", object()))
    assert claimed["status"] == "claimed" and claimed["claimed_by_operator_user_id"] == "support-1"
    assert asyncio.run(inbox(object()))["cases"][0]["status"] == "claimed"
    body["expected_revision"] = claimed["revision"]
    body["idempotency_key"] = "op-resolve-1"
    resolved = asyncio.run(mutate(case["id"], "resolve", object()))
    assert resolved["status"] == "resolved"
    assert asyncio.run(inbox(object()))["cases"][0]["status"] == "resolved"
    assert registry.list(tenant_id="tenant-b", business_id="business-a") == []


def test_operator_route_fails_closed_for_owner_and_wrong_business_binding(monkeypatch):
    _, router, current, body = _fixture(monkeypatch)
    queue = _endpoint(router, "/platform-support/cases", "GET")
    current["principal"] = SimpleNamespace(
        actor_id="owner", subject="owner", roles=(RoleId.OWNER,),
        scopes=("support_case_manage",), tenant_id="tenant-a",
        metadata={"business_id": "business-a"},
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(queue(object()))
    assert (exc.value.status_code, exc.value.detail) == (403, "support_case_operator_scope_required")
    current["principal"].roles = (RoleId.SUPPORT,)
    current["principal"].scopes = ()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(queue(object()))
    assert exc.value.status_code == 403
    current["principal"].scopes = ("support_case_manage",)
    current["principal"].metadata = {}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(queue(object()))
    assert exc.value.status_code == 403


def test_support_route_rejects_conflicts_and_unexpected_fields(monkeypatch):
    _, router, _, body = _fixture(monkeypatch)
    create = _endpoint(router, "/business-workspace/support-cases", "POST")
    first = asyncio.run(create(object()))
    body["summary"] = "A different request with a reused key"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(create(object()))
    assert (exc.value.status_code, exc.value.detail) == (409, "support_case_idempotency_conflict")
    body["tenant_id"] = "attacker-tenant"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(create(object()))
    assert exc.value.status_code == 422
    body.clear()
    body.update({"expected_revision": first["revision"], "idempotency_key": "claim-1"})
    transition = _endpoint(router, "/platform-support/cases/{case_id}/{action}", "POST")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(transition(first["id"], "resolve", object()))
    assert (exc.value.status_code, exc.value.detail) == (409, "support_case_not_claimed_by_operator")
