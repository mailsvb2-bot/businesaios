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


    @router.get("/business-workspace/programs/{program_id}/enrollments", tags=["business-workspace"])
    async def list_program_enrollments(program_id: str, request: Request):
        tenant_id, business_id, _ = scope(request)
        try:
            return {"enrollments": programs.list_enrollments(
                tenant_id=tenant_id, business_id=business_id, program_id=program_id,
            )}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="program_not_found") from exc

    @router.post("/business-workspace/programs/{program_id}/enrollments", tags=["business-workspace"])
    async def enroll_program_customer(program_id: str, request: Request):
        tenant_id, business_id, actor_id = scope(request)
        body = await json_body(request)
        if set(body) != {"customer_id"} or not isinstance(body.get("customer_id"), str):
            raise HTTPException(status_code=422, detail="enrollment_fields_invalid")
        try:
            return programs.enroll_customer(
                tenant_id=tenant_id, business_id=business_id, actor_id=actor_id,
                program_id=program_id, customer_id=body["customer_id"],
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            if str(exc) in {"enrollment_program_not_active", "enrollment_customer_not_active"}:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if str(exc) == "enrollment_canonical_customer_owner_unavailable":
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            raise

    @router.get("/business-workspace/program-drafts", tags=["business-workspace"])
    async def list_program_drafts(request: Request):
        tenant_id, business_id, _ = scope(request)
        return {"drafts": programs.list_drafts(tenant_id=tenant_id, business_id=business_id)}

    @router.post("/business-workspace/program-drafts", tags=["business-workspace"])
    async def create_program_draft(request: Request):
        tenant_id, business_id, actor_id = scope(request)
        body = await json_body(request)
        if set(body) != {"title", "lessons", "idempotency_key"}:
            raise HTTPException(status_code=422, detail="program_draft_fields_invalid")
        try:
            return programs.create_draft(
                tenant_id=tenant_id, business_id=business_id, actor_id=actor_id,
                title=body["title"], lessons=body["lessons"],
                idempotency_key=body["idempotency_key"],
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            if str(exc) == "program_idempotency_conflict":
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise

    @router.post("/business-workspace/program-drafts/{program_id}", tags=["business-workspace"])
    async def change_program_draft(program_id: str, request: Request):
        tenant_id, business_id, actor_id = scope(request)
        body = await json_body(request)
        action = body.get("action")
        expected = {"action", "expected_revision", "idempotency_key"}
        if action == "save":
            expected |= {"title", "lessons"}
        if set(body) != expected:
            raise HTTPException(status_code=422, detail="program_draft_transition_fields_invalid")
        try:
            return programs.change_draft(
                tenant_id=tenant_id, business_id=business_id, actor_id=actor_id,
                program_id=program_id, action=action,
                expected_revision=body["expected_revision"],
                idempotency_key=body["idempotency_key"],
                title=body.get("title"), lessons=body.get("lessons"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="program_not_found") from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            if str(exc) in {"program_revision_conflict", "program_idempotency_conflict",
                            "program_draft_not_editable"} or str(exc).startswith("ontology transition rejected:"):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise


__all__ = ["register_business_workspace_program_routes"]
