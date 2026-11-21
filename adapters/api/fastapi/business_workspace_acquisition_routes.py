from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from acquisition import evaluate_acquisition_payload
from adapters.api.fastapi.router_support import business_owner_scope, json_body
from interfaces.ads.registry import CONNECTORS
from presentation import build_acquisition_view_model

CANON_BUSINESS_WORKSPACE_ACQUISITION_ROUTES = True


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


def register_business_workspace_acquisition_routes(*, router: APIRouter, auth_bundle) -> None:
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
            'ok': True, 'tenant_id': tenant_id, 'business_id': business_id,
            'assumption_source': 'owner_input', 'calculation_only': True,
            'write_actions_enabled': False,
            'ad_provider_truth': {name: {'production_ready': bool(row['production_ready']), 'write': bool(row['write']), 'verify': bool(row['verify'])} for name, row in CONNECTORS.items()},
            'ad_provider_capability_ready': any(row['production_ready'] and row['write'] and row['verify'] for row in CONNECTORS.values()),
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


    @router.post('/business-workspace/acquisition-plan/launch', tags=['business-workspace'])
    async def acquisition_launch(request: Request) -> dict[str, Any]:
        from config.env_flags import env_bool
        from headless.acquisition_execution import promotion_launch_preview

        if not env_bool('BAI_PROMOTION_LAUNCH_ENABLED', False):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='promotion_launch_disabled')
        _, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        if not isinstance(body, dict) or not isinstance(body.get('plan_input'), dict):
            raise HTTPException(status_code=422, detail='promotion_launch_plan_input_required')
        mode, provider = body.get('mode', 'dry_run'), str(body.get('provider') or 'yandex_direct')
        if mode not in {'dry_run', 'apply'} or set(body) - {'plan_input', 'mode', 'provider'}:
            raise HTTPException(status_code=422, detail='promotion_launch_fields_invalid')
        try:
            result = evaluate_acquisition_payload(body['plan_input'])
            view = build_acquisition_view_model(result)
        except (TypeError, ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        preview = promotion_launch_preview(plan=asdict(view), sustainable=bool(result.cac.sustainable),
                                           provider=provider, connectors=CONNECTORS)
        if mode == 'apply':
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                'error': 'promotion_apply_blocked' if preview['blockers'] else 'promotion_apply_requires_governed_approval',
                'blockers': preview['blockers']})
        return _json_safe({'ok': True, 'tenant_id': tenant_id, 'business_id': business_id, **preview})


__all__ = ['CANON_BUSINESS_WORKSPACE_ACQUISITION_ROUTES', 'register_business_workspace_acquisition_routes']
