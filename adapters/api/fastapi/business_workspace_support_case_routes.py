"""Authenticated Phase-18 support journey; no cross-tenant operator bypass."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import authorize_request, business_owner_scope, json_body
from application.business_autonomy.support_case_registry import SupportCaseRegistry
from governance.rbac_contract import RoleId


def register_business_workspace_support_case_routes(
    *, router: APIRouter, auth_bundle, support_cases: SupportCaseRegistry,
) -> None:
    def owner(request: Request):
        principal, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
        actor_id = str(getattr(principal, "actor_id", None) or getattr(principal, "subject", "") or "").strip()
        if not actor_id:
            raise HTTPException(status_code=403, detail="support_case_actor_required")
        return tenant_id, business_id, actor_id

    def operator(request: Request):
        _, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        if RoleId.SUPPORT not in tuple(principal.roles) or "support_case_manage" not in tuple(principal.scopes):
            raise HTTPException(status_code=403, detail="support_case_operator_scope_required")
        tenant_id = str(principal.tenant_id or "").strip()
        business_id = str(dict(principal.metadata or {}).get("business_id") or "").strip()
        actor_id = str(getattr(principal, "actor_id", None) or getattr(principal, "subject", "") or "").strip()
        if not all((tenant_id, business_id, actor_id)):
            raise HTTPException(status_code=403, detail="support_case_operator_binding_required")
        return tenant_id, business_id, actor_id

    def fail(exc: Exception):
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail="support_case_not_found") from exc
        if isinstance(exc, (ValueError, TypeError)):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if isinstance(exc, RuntimeError) and str(exc).startswith("support_case_"):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise exc

    @router.get("/business-workspace/support-cases", tags=["business-workspace"])
    async def owner_list_support_cases(request: Request, limit: int = 50):
        tenant_id, business_id, _ = owner(request)
        try:
            return {"cases": support_cases.list(tenant_id=tenant_id, business_id=business_id, limit=limit)}
        except (ValueError, RuntimeError) as exc:
            fail(exc)

    @router.post("/business-workspace/support-cases", tags=["business-workspace"])
    async def owner_create_support_case(request: Request):
        tenant_id, business_id, actor_id = owner(request)
        body = await json_body(request)
        if set(body) != {"category", "summary", "idempotency_key"}:
            raise HTTPException(status_code=422, detail="support_case_create_fields_invalid")
        try:
            return support_cases.create(
                tenant_id=tenant_id, business_id=business_id, actor_id=actor_id,
                category=body["category"], summary=body["summary"],
                idempotency_key=body["idempotency_key"],
            )
        except (ValueError, TypeError, RuntimeError, KeyError) as exc:
            fail(exc)

    @router.get("/platform-support/cases", tags=["platform-support"])
    async def operator_queue(request: Request, limit: int = 50):
        tenant_id, business_id, _ = operator(request)
        try:
            return {"cases": support_cases.list(tenant_id=tenant_id, business_id=business_id, limit=limit)}
        except (ValueError, RuntimeError) as exc:
            fail(exc)

    @router.post("/platform-support/cases/{case_id}/{action}", tags=["platform-support"])
    async def operator_transition(case_id: str, action: str, request: Request):
        tenant_id, business_id, actor_id = operator(request)
        body = await json_body(request)
        if set(body) != {"expected_revision", "idempotency_key"}:
            raise HTTPException(status_code=422, detail="support_case_transition_fields_invalid")
        try:
            return support_cases.transition(
                tenant_id=tenant_id, business_id=business_id, case_id=case_id,
                operator_id=actor_id, action=action,
                expected_revision=body["expected_revision"],
                idempotency_key=body["idempotency_key"],
            )
        except (ValueError, TypeError, RuntimeError, KeyError) as exc:
            fail(exc)
