"""Owner-scoped organization lifecycle over the existing canonical event writer."""

from __future__ import annotations

from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5
from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.organization.projector import OrganizationProjector
from application.organization.registry import OrganizationRegistry


def register_business_workspace_organization_routes(
    *, router: APIRouter, auth_bundle, event_store, idempotency_store,
) -> None:
    projector = OrganizationProjector(event_store)
    registry = OrganizationRegistry(event_store=event_store, idempotency_store=idempotency_store)

    @router.get("/business-workspace/organizations", tags=["business-workspace"])
    async def organizations(request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane",
        )
        return {
            "tenant_id": tenant_id,
            "business_id": business_id,
            "organizations": [
                asdict(item) for item in projector.list_for_business(
                    tenant_id=tenant_id, business_id=business_id,
                )
            ],
        }

    @router.post("/business-workspace/organizations", tags=["business-workspace"])
    async def create_organization(request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane",
        )
        body = await json_body(request)
        if set(body) - {"name", "organization_type", "organization_id"}:
            raise HTTPException(status_code=422, detail="organization_unknown_fields")
        name = body.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 300:
            raise HTTPException(status_code=422, detail="organization_name_required")
        org_id = body.get("organization_id")
        if org_id is not None and (not isinstance(org_id, str) or not org_id.strip()):
            raise HTTPException(status_code=422, detail="organization_id_invalid")
        org_type = body.get("organization_type")
        if org_type is not None and not isinstance(org_type, str):
            raise HTTPException(status_code=422, detail="organization_type_invalid")
        key = request.headers.get("x-idempotency-key", "").strip()
        if not key or len(key) > 200:
            raise HTTPException(status_code=422, detail="idempotency_key_required")
        # Stable identity derived from the provided request key prevents duplicates on retries.
        stable_id = str(uuid5(NAMESPACE_URL, f"organization:{tenant_id}:{business_id}:{key}"))
        if org_id is not None and org_id != stable_id:
            raise HTTPException(status_code=422, detail="organization_id_must_match_idempotency_key")
        try:
            item = registry.create(
                tenant_id=tenant_id, business_id=business_id,
                organization_id=stable_id, idempotency_key=key,
                name=name.strip(), organization_type=org_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"organization": asdict(item), "tenant_id": tenant_id, "business_id": business_id}


__all__ = ["register_business_workspace_organization_routes"]
