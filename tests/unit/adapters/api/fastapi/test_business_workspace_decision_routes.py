from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_decision_routes as routes
from adapters.api.fastapi import router_support
from entrypoints.api.owner_action_draft import OwnerActionDraftError
from governance.rbac_contract import RoleId


class _Projector:
    def __init__(self) -> None:
        self.kwargs = None

    def project(self, **kwargs):
        self.kwargs = dict(kwargs)
        return {"source": "decision_core_ledger", "execution_allowed": False}


def _principal():
    return SimpleNamespace(tenant_id="tenant-session", subject="owner-user", actor_id="owner-user", roles=(RoleId.OWNER,), scopes=("provider_control_plane",), metadata={"business_id": "business-session", "principal_kind": "user"})


def _endpoint(router: APIRouter):
    return next(route.endpoint for route in router.routes if getattr(route, "path", None) == "/business-workspace/decision-draft")


def test_decision_draft_uses_authenticated_owner_scope_not_browser_scope(monkeypatch) -> None:
    projector, router = _Projector(), APIRouter()
    routes.register_business_workspace_decision_routes(router=router, auth_bundle=object(), projector=projector)
    monkeypatch.setattr(router_support, "authorize_request", lambda **_: (object(), _principal()))

    async def body(_request):
        return {"tenant_id": "tenant-victim", "business_id": "business-victim", "run_id": "run-1", "decision_id": "decision-1", "action_id": "action-1"}

    monkeypatch.setattr(routes, "json_body", body)
    result = asyncio.run(_endpoint(router)(object()))
    assert result["execution_allowed"] is False
    assert projector.kwargs == {"tenant_id": "tenant-session", "business_id": "business-session", "run_id": "run-1", "decision_id": "decision-1", "action_id": "action-1"}


def test_decision_draft_maps_projection_error_without_execution(monkeypatch) -> None:
    class _Failing:
        def project(self, **_kwargs):
            raise OwnerActionDraftError("decision_action_already_executed")

    router = APIRouter()
    routes.register_business_workspace_decision_routes(router=router, auth_bundle=object(), projector=_Failing())
    monkeypatch.setattr(router_support, "authorize_request", lambda **_: (object(), _principal()))

    async def body(_request):
        return {"run_id": "run-1", "decision_id": "decision-1", "action_id": "action-1"}

    monkeypatch.setattr(routes, "json_body", body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_endpoint(router)(object()))
    assert (exc.value.status_code, exc.value.detail) == (409, "decision_action_already_executed")
