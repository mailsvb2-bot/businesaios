from __future__ import annotations

from fastapi import Request
from entrypoints.api.request_context import RequestContext
from application.public_site.cta_intake import CTALandingIntakeService


def _cta_submit_response(result) -> dict:
    return {
        'ok': True, 'intake_id': result.intake_id, 'created_at': result.created_at,
        'tenant_id': result.tenant_id, 'business_id': result.business_id, 'user_id': result.user_id,
        'onboarding_status': result.onboarding_status, 'next': {'ui_url': result.app_url},
        'next_actions': list(result.next_actions), 'user_functionality': dict(result.user_functionality or {}),
        'admin_visibility': dict(result.admin_visibility or {}), 'measurable_outcome': result.outcome,
        'write_actions_enabled': False, 'approval_required_before_execution': True,
    }


def _cta_status_response(status_payload) -> dict:
    if not status_payload.found:
        return {'ok': False, 'error': 'not_found', 'intake_id': status_payload.intake_id}
    return {
        'ok': True, 'intake_id': status_payload.intake_id, 'found': status_payload.found,
        'created_at': status_payload.created_at, 'tenant_id': status_payload.tenant_id,
        'business_id': status_payload.business_id, 'user_id': status_payload.user_id,
        'onboarding_status': status_payload.onboarding_status, 'next_actions': list(status_payload.next_actions),
        'user_functionality': dict(status_payload.user_functionality or {}),
        'admin_visibility': dict(status_payload.admin_visibility or {}), 'measurable_outcome': status_payload.outcome,
        'write_actions_enabled': False, 'approval_required_before_execution': True,
    }


def register_public_site_routes(*, router, enforce_public_security) -> None:
    cta_intake_service = CTALandingIntakeService()

    @router.post('/public-site/cta/start', tags=['public-site'])
    async def public_site_cta_start(http_request: Request) -> dict:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/public-site/cta/start'})
        try:
            payload = await http_request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        enforce_public_security(route_path='/public-site/cta/start', request_context=request_context, body=payload, http_request=http_request)
        result = cta_intake_service.submit(payload=payload)
        return _cta_submit_response(result)

    @router.get('/public-site/cta/{intake_id}', tags=['public-site'])
    async def public_site_cta_status(http_request: Request, intake_id: str) -> dict:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/public-site/cta/{intake_id}'})
        enforce_public_security(route_path='/public-site/cta/{intake_id}', request_context=request_context, body={'intake_id': intake_id}, http_request=http_request)
        return _cta_status_response(cta_intake_service.get_status(intake_id=intake_id))
