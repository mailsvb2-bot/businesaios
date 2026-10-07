from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from acquisition import evaluate_acquisition_payload
from application.campaign.registry import EventPromotionTarget, event_advertising_url
from adapters.api.fastapi.router_support import business_owner_scope, json_body
from presentation import build_acquisition_view_model

CANON_BUSINESS_WORKSPACE_ACQUISITION_ROUTES = True


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def register_business_workspace_acquisition_routes(*, router: APIRouter, auth_bundle, event_landing_registry=None) -> None:
    @router.post('/business-workspace/event-promotion-target', tags=['business-workspace'])
    async def event_promotion_target(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        allowed = {'event_id', 'public_base_url'}
        if set(body).difference(allowed):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='event_promotion_unknown_fields')
        try:
            event_id = str(body.get('event_id') or '').strip()
            if event_landing_registry is None:
                raise RuntimeError('event_landing_registry_unavailable')
            state = event_landing_registry.get(tenant_id=tenant_id, business_id=business_id, event_id=event_id)
            if state.public_content() is None:
                raise ValueError('event_landing_not_published')
            target = EventPromotionTarget(
                event_id=event_id,
                tenant_id=tenant_id,
                business_id=business_id,
                public_base_url=str(body.get('public_base_url') or '').strip(),
            )
            url = event_advertising_url(target)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else 'event_landing_not_found')) from exc
        except RuntimeError as exc:
            if str(exc) == 'event_landing_registry_unavailable':
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
            raise
        except ValueError as exc:
            code = str(exc)
            http_status = status.HTTP_409_CONFLICT if code == 'event_landing_not_published' else status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=http_status, detail=code) from exc
        return {
            'ok': True,
            'tenant_id': tenant_id,
            'business_id': business_id,
            'event_id': target.event_id,
            'destination_url': url,
            'source': 'canonical_public_event_route',
            'calculation_only': True,
            'write_actions_enabled': False,
        }

    @router.post('/business-workspace/acquisition-plan', tags=['business-workspace'])
    async def acquisition_plan(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        try:
            result = evaluate_acquisition_payload(body)
            view = build_acquisition_view_model(result)
        except (TypeError, ValueError, OverflowError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return _json_safe({
            'ok': True,
            'tenant_id': tenant_id,
            'business_id': business_id,
            'assumption_source': 'owner_input',
            'calculation_only': True,
            'write_actions_enabled': False,
            'plan': asdict(view),
            'economics': {
                'feasibility_score': result.feasibility_score,
                'overall_conversion_rate': result.funnel.overall_conversion_rate,
                'blended_cac': result.cac.blended_cac,
                'max_sustainable_cac': result.cac.max_sustainable_cac,
                'ltv_to_cac_ratio': result.cac.ltv_to_cac_ratio,
                'payback_months': result.cac.payback_months,
                'sustainable': result.cac.sustainable,
            },
        })


__all__ = ['CANON_BUSINESS_WORKSPACE_ACQUISITION_ROUTES', 'register_business_workspace_acquisition_routes']
