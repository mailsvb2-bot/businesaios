from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from acquisition import evaluate_acquisition_payload
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


def register_business_workspace_acquisition_routes(*, router: APIRouter, auth_bundle) -> None:
    @router.post('/business-workspace/acquisition-plan', tags=['business-workspace'])
    async def acquisition_plan(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        try:
            result = evaluate_acquisition_payload(body)
            view = build_acquisition_view_model(result)
        except (TypeError, ValueError) as exc:
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
