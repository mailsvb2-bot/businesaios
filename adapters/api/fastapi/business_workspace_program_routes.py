"""Owner-scoped multi-lesson publication from ClientPlatform into canonical Business Facts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry


def register_business_workspace_program_routes(
    *, router: APIRouter, auth_bundle, programs: ProgramPublicationRegistry,
) -> None:
    def scope(request: Request) -> tuple[str, str, str]:
        principal, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle,
        )
        actor_id = str(principal.actor_id or principal.subject or "").strip()
        if not actor_id:
            raise HTTPException(status_code=403, detail="program_actor_required")
        return tenant_id, business_id, actor_id

    @router.get("/business-workspace/programs", tags=["business-workspace"])
    async def list_programs(request: Request, limit: int = 50):
        tenant_id, business_id, _ = scope(request)
        try:
            return {"programs": programs.list_for_business(
                tenant_id=tenant_id, business_id=business_id, limit=limit,
            )}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/business-workspace/programs", tags=["business-workspace"])
    async def publish_program(request: Request):
        tenant_id, business_id, actor_id = scope(request)
        body = await json_body(request)
        if set(body) != {"title", "lessons", "idempotency_key"}:
            raise HTTPException(status_code=422, detail="program_publication_fields_invalid")
        try:
            return programs.publish(
                tenant_id=tenant_id, business_id=business_id, actor_id=actor_id,
                title=body["title"], lessons=body["lessons"],
                idempotency_key=body["idempotency_key"],
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            if str(exc) == "program_idempotency_conflict":
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise

    @router.get("/business-workspace/programs/{program_id}", tags=["business-workspace"])
    async def get_program(program_id: str, request: Request):
        tenant_id, business_id, _ = scope(request)
        try:
            return programs.get(
                tenant_id=tenant_id, business_id=business_id, program_id=program_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="program_not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = ["register_business_workspace_program_routes"]
