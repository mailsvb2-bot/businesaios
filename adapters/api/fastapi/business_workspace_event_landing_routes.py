from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.public_site.event_landing_registry import EventLandingRegistry, event_landing_payload
from contracts.landing_page import EventLandingContent


def register_business_workspace_event_landing_routes(*, router: APIRouter, auth_bundle, registry: EventLandingRegistry) -> None:
    def scope(request: Request):
        principal,tenant_id,business_id=business_owner_scope(request=request,auth_bundle=auth_bundle)
        return principal,tenant_id,business_id

    @router.get('/business-workspace/event-landings/{event_id}', tags=['business-workspace'])
    async def get_event_landing(event_id: str, request: Request):
        _,tenant_id,business_id=scope(request)
        try:
            return event_landing_payload(registry.get(tenant_id=tenant_id,business_id=business_id,event_id=event_id))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='event_landing_not_found') from exc

    @router.post('/business-workspace/event-landings/{event_id}', tags=['business-workspace'])
    async def mutate_event_landing(event_id: str, request: Request):
        principal,tenant_id,business_id=scope(request)
        body=await json_body(request)
        allowed={'action','content','source','expected_revision','idempotency_key'}
        if set(body)-allowed:
            raise HTTPException(status_code=422,detail='event_landing_unknown_fields')
        action=str(body.get('action') or '').strip()
        idem=str(body.get('idempotency_key') or '').strip()
        if not idem: raise HTTPException(status_code=422,detail='idempotency_key_required')
        actor=str(getattr(principal,'actor_id',None) or getattr(principal,'subject','') or 'owner')
        try:
            if action=='create':
                content=EventLandingContent.from_payload(body.get('content'))
                state=registry.create(tenant_id=tenant_id,business_id=business_id,event_id=event_id,content=content,source=str(body.get('source') or 'manual'),idempotency_key=idem,actor_id=actor)
            else:
                rev=body.get('expected_revision')
                if isinstance(rev,bool) or not isinstance(rev,int): raise ValueError('expected_revision_required')
                content=EventLandingContent.from_payload(body.get('content')) if action=='save' else None
                state=registry.transition(tenant_id=tenant_id,business_id=business_id,event_id=event_id,action=action,expected_revision=rev,idempotency_key=idem,actor_id=actor,content=content,source=str(body.get('source') or 'manual'))
            return event_landing_payload(state)
        except RuntimeError as exc:
            if 'revision_conflict' in str(exc): raise HTTPException(status_code=409,detail='event_landing_revision_conflict') from exc
            raise
        except (TypeError,ValueError) as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc
