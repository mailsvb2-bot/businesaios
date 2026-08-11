from __future__ import annotations

from dataclasses import asdict

from fastapi import HTTPException, Request, status

from acquisition import evaluate_acquisition_plan, request_from_payload
from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace
from entrypoints.api.request_context import RequestContext
from presentation import build_acquisition_view_model
from tenancy.tenant_registry import ensure_tenant_record


def _product_fields(value) -> dict:
    return {
        'business_profile': dict(getattr(value, 'business_profile', None) or {}), 'selected_providers': list(getattr(value, 'selected_providers', ()) or ()),
        'integration_plan': list(getattr(value, 'integration_plan', ()) or ()), 'autonomy_mode': str(getattr(value, 'autonomy_mode', 'advisor') or 'advisor'),
        'first_value_preview': dict(getattr(value, 'first_value_preview', None) or {}), 'onboarding_progress': dict(getattr(value, 'onboarding_progress', None) or {})}


def _base_response(value) -> dict:
    return {
        'ok': True, 'intake_id': value.intake_id, 'created_at': value.created_at, 'tenant_id': value.tenant_id, 'business_id': value.business_id,
        'user_id': value.user_id, 'onboarding_status': value.onboarding_status, 'next_actions': list(value.next_actions),
        'user_functionality': dict(value.user_functionality or {}), 'admin_visibility': dict(value.admin_visibility or {}), 'measurable_outcome': value.outcome,
        'write_actions_enabled': False, 'approval_required_before_execution': True, **_product_fields(value)}


def _cta_submit_response(result, owner_session: dict | None = None) -> dict:
    payload = {**_base_response(result), 'next': {'ui_url': result.app_url}}
    return {**payload, 'owner_session': owner_session} if owner_session else payload


def _cta_status_response(status_payload) -> dict:
    return {**_base_response(status_payload), 'found': True} if status_payload.found else {'ok': False, 'error': 'not_found', 'intake_id': status_payload.intake_id}


def register_public_site_routes(*, router, enforce_public_security, auth_bundle=None, tenant_registry=None) -> None:
    service = CTALandingIntakeService()

    def secure(request: Request, route: str, body: dict) -> None:
        enforce_public_security(route_path=route, request_context=RequestContext.from_http_request(request, metadata={'route': route}), body=body, http_request=request)

    @router.get('/public-site/integrations', tags=['public-site'])
    async def public_site_integrations(http_request: Request) -> dict:
        secure(http_request, '/public-site/integrations', {})
        rows = public_integration_marketplace()
        return {'ok': True, 'items': list(rows), 'total': len(rows), 'policy': {'initial_sync': 'read_only', 'write_actions_enabled': False, 'credential_activation_requires_authenticated_control_plane': True}}

    @router.post('/public-site/acquisition/feasibility', tags=['public-site', 'acquisition'])
    async def public_site_acquisition_feasibility(http_request: Request) -> dict:
        try:
            body = await http_request.json()
        except Exception:
            body = {}
        body = body if isinstance(body, dict) else {}
        secure(http_request, '/public-site/acquisition/feasibility', body)
        try:
            result = evaluate_acquisition_plan(request_from_payload(body))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        view = build_acquisition_view_model(result)
        return {
            'ok': True,
            'scenario_source': 'user_assumptions',
            'write_actions_enabled': False,
            'disclaimer': 'Сценарный расчёт по введённым предположениям; это не подтверждённые метрики бизнеса.',
            'view': asdict(view),
            'economics': {
                'feasibility_score': result.feasibility_score,
                'overall_conversion_rate': result.funnel.overall_conversion_rate,
                'blended_cac': result.cac.blended_cac,
                'max_sustainable_cac': result.cac.max_sustainable_cac,
                'ltv_to_cac_ratio': result.cac.ltv_to_cac_ratio,
                'payback_months': result.cac.payback_months,
                'sustainable': result.cac.sustainable,
            },
        }

    @router.post('/public-site/cta/start', tags=['public-site'])
    async def public_site_cta_start(http_request: Request) -> dict:
        try:
            payload = await http_request.json()
        except Exception:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        secure(http_request, '/public-site/cta/start', payload)
        result = service.submit(payload=payload)
        owner_session = None
        api_key_policy = getattr(getattr(auth_bundle, 'auth_policy', None), 'api_key_policy', None)
        if tenant_registry is not None and api_key_policy is not None:
            ensure_tenant_record(tenant_registry, result.tenant_id, display_name=str((result.business_profile or {}).get('name') or result.tenant_id))
            record, raw_key = api_key_policy.issue_owner_session(tenant_id=result.tenant_id, business_id=result.business_id, subject=result.user_id, display_name=str((result.business_profile or {}).get('name') or '') or None)
            owner_session = {'api_key': raw_key, 'tenant_id': result.tenant_id, 'business_id': result.business_id, 'expires_at': None if record.expires_at is None else record.expires_at.isoformat(), 'storage': 'session_only'}
        return _cta_submit_response(result, owner_session)

    @router.get('/public-site/cta/{intake_id}', tags=['public-site'])
    async def public_site_cta_status(http_request: Request, intake_id: str) -> dict:
        secure(http_request, '/public-site/cta/{intake_id}', {'intake_id': intake_id})
        return _cta_status_response(service.get_status(intake_id=intake_id))
