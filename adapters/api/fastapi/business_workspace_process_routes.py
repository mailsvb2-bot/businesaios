from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.process_discovery import (
    CanonicalProcessWorkspace,
    ProcessRequestIdempotency,
    ProcessRequestIdempotencyError,
    ProcessWorkspaceError,
)
from entrypoints.api.headless_models import ExecuteGoalRequest
from entrypoints.api.request_context import RequestContext

CANON_BUSINESS_WORKSPACE_PROCESS_ROUTES = True


def _raise_workspace_error(exc: ProcessWorkspaceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


def _raise_idempotency_error(exc: ProcessRequestIdempotencyError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


def _idempotency_key(request: Request) -> str:
    return str(request.headers.get("x-idempotency-key") or request.headers.get("idempotency-key") or "").strip()


def _begin(
    *, idempotency: ProcessRequestIdempotency, tenant_id: str, operation: str, raw_key: str, semantic_scope: Mapping[str, Any]
):
    try:
        return idempotency.begin(
            tenant_id=tenant_id, operation=operation, raw_key=raw_key, semantic_scope=semantic_scope,
        )
    except ProcessRequestIdempotencyError as exc:
        _raise_idempotency_error(exc)


def _mark_failed(idempotency: ProcessRequestIdempotency, lease, reason: object) -> None:
    try:
        idempotency.fail(lease=lease, reason=str(reason or "process_request_failed"))
    except Exception:
        return


def register_business_workspace_process_routes(
    *,
    router: APIRouter,
    auth_bundle,
    workspace: CanonicalProcessWorkspace,
    headless_handlers,
    request_idempotency: ProcessRequestIdempotency,
    enforce_public_security: Callable[..., RequestContext],
) -> None:
    @router.post("/business-workspace/process-observations", tags=["business-workspace"])
    async def record_process_observation(request: Request) -> dict:
        principal, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane"
        )
        body = await json_body(request)
        raw_key = _idempotency_key(request)
        lease = _begin(
            idempotency=request_idempotency, tenant_id=tenant_id, operation="record_observation", raw_key=raw_key,
            semantic_scope={"business_id": business_id, "payload": body},
        )
        if lease.replay_payload is not None:
            return lease.replay_payload
        user_id = str(getattr(principal, "subject_id", None) or getattr(principal, "user_id", None) or "owner")
        try:
            result = workspace.record_observation(
                tenant_id=tenant_id, business_id=business_id, user_id=user_id, payload=body, request_id=raw_key,
            )
        except ProcessWorkspaceError as exc:
            _mark_failed(request_idempotency, lease, exc.code)
            _raise_workspace_error(exc)
        request_idempotency.complete(lease=lease, payload=result)
        return result

    @router.get("/business-workspace/process-opportunities", tags=["business-workspace"])
    async def process_opportunities(request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane"
        )
        try:
            return workspace.discover(tenant_id=tenant_id, business_id=business_id)
        except ProcessWorkspaceError as exc:
            _raise_workspace_error(exc)

    @router.post(
        "/business-workspace/process-opportunities/{opportunity_id}/blueprint",
        tags=["business-workspace"],
    )
    async def build_process_blueprint(opportunity_id: str, request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane"
        )
        body = await json_body(request)
        clean_opportunity_id = str(opportunity_id or "").strip()
        lease = _begin(
            idempotency=request_idempotency, tenant_id=tenant_id, operation="build_blueprint",
            raw_key=_idempotency_key(request),
            semantic_scope={"business_id": business_id, "opportunity_id": clean_opportunity_id, "payload": body},
        )
        if lease.replay_payload is not None:
            return lease.replay_payload
        try:
            result = workspace.build(
                tenant_id=tenant_id, business_id=business_id, opportunity_id=clean_opportunity_id, payload=body,
            )
        except ProcessWorkspaceError as exc:
            _mark_failed(request_idempotency, lease, exc.code)
            _raise_workspace_error(exc)
        request_idempotency.complete(lease=lease, payload=result)
        return result

    @router.post(
        "/business-workspace/process-blueprints/{blueprint_id}/decision",
        tags=["business-workspace"],
    )
    async def run_process_blueprint_decision(blueprint_id: str, request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane"
        )
        clean_blueprint_id = str(blueprint_id or "").strip()
        try:
            advisory = workspace.decision_request(
                tenant_id=tenant_id, business_id=business_id, blueprint_id=clean_blueprint_id,
            )
        except ProcessWorkspaceError as exc:
            _raise_workspace_error(exc)
        goal_request = ExecuteGoalRequest(
            goal=str(advisory["objective"]),
            business_id=business_id,
            tenant_id=tenant_id,
            max_steps=1,
            meta={
                "source": "owner_workspace",
                "process_blueprint_id": str(advisory["blueprint_id"]),
                "process_baseline_fingerprint": str(advisory["baseline_fingerprint"]),
                "server_bound_process_blueprint": True,
            },
        )
        enforce_public_security(
            route_path="/goals/execute",
            request_context=RequestContext.from_http_request(request, metadata={"route": "/goals/execute"}),
            body=goal_request.model_dump(),
            http_request=request,
        )
        lease = _begin(
            idempotency=request_idempotency, tenant_id=tenant_id, operation="run_blueprint_decision",
            raw_key=_idempotency_key(request),
            semantic_scope={"business_id": business_id, "blueprint_id": clean_blueprint_id},
        )
        if lease.replay_payload is not None:
            return lease.replay_payload
        try:
            result = headless_handlers.execute_goal(goal_request)
            result_payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
            workspace.bind_decision_result(
                tenant_id=tenant_id, business_id=business_id, blueprint_id=clean_blueprint_id, result=result_payload,
            )
        except ProcessWorkspaceError as exc:
            _mark_failed(request_idempotency, lease, exc.code)
            _raise_workspace_error(exc)
        except Exception as exc:
            _mark_failed(request_idempotency, lease, exc.__class__.__name__)
            raise
        request_idempotency.complete(lease=lease, payload=result_payload)
        return result_payload

    @router.get(
        "/business-workspace/process-blueprints/{blueprint_id}/measurement",
        tags=["business-workspace"],
    )
    async def measure_process_blueprint(blueprint_id: str, request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(
            request=request, auth_bundle=auth_bundle, required_scope="provider_control_plane"
        )
        try:
            return workspace.measure(
                tenant_id=tenant_id, business_id=business_id, blueprint_id=str(blueprint_id or "").strip(),
            )
        except ProcessWorkspaceError as exc:
            _raise_workspace_error(exc)


__all__ = ["CANON_BUSINESS_WORKSPACE_PROCESS_ROUTES", "register_business_workspace_process_routes"]
