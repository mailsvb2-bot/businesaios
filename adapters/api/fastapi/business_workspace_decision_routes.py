from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from entrypoints.api.owner_action_draft import OwnerActionDraftError, OwnerActionDraftProjector

CANON_BUSINESS_WORKSPACE_DECISION_ROUTES = True


def register_business_workspace_decision_routes(*, router: APIRouter, auth_bundle, projector: OwnerActionDraftProjector) -> None:
    @router.post('/business-workspace/decision-draft', tags=['business-workspace'])
    async def decision_draft(request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle, required_scope='provider_control_plane')
        body = await json_body(request)
        try:
            return projector.project(
                tenant_id=tenant_id,
                business_id=business_id,
                run_id=str(body.get('run_id') or ''),
                decision_id=str(body.get('decision_id') or ''),
                action_id=str(body.get('action_id') or ''),
            )
        except OwnerActionDraftError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


__all__ = ['CANON_BUSINESS_WORKSPACE_DECISION_ROUTES', 'register_business_workspace_decision_routes']
