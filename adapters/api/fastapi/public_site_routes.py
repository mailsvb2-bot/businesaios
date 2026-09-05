from __future__ import annotations

from fastapi import HTTPException, Request, Response, status

from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace
from entrypoints.api.request_context import RequestContext
from tenancy.tenant_registry import ensure_tenant_record

_OWNER_RESUME_COOKIE = 'businessaios_owner_resume'
_OWNER_RESUME_TTL_SECONDS = 86400
_OWNER_ACCOUNT_COOKIE = 'businessaios_owner_account'
_OWNER_ACCOUNT_TTL_SECONDS = 86400


def _product_fields(value) -> dict:
    return {
        'business_profile': dict(getattr(value, 'business_profile', None) or {}),
        'selected_providers': list(getattr(value, 'selected_providers', ()) or ()),
        'integration_plan': list(getattr(value, 'integration_plan', ()) or ()),
        'autonomy_mode': str(getattr(value, 'autonomy_mode', 'advisor') or 'advisor'),
        'first_value_preview': dict(getattr(value, 'first_value_preview', None) or {}),
        'onboarding_progress': dict(getattr(value, 'onboarding_progress', None) or {}),
    }


def _base_response(value) -> dict:
    return {
        'ok': True,
        'intake_id': value.intake_id,
        'created_at': value.created_at,
        'tenant_id': value.tenant_id,
        'business_id': value.business_id,
        'user_id': value.user_id,
        'onboarding_status': value.onboarding_status,
        'next_actions': list(value.next_actions),
        'user_functionality': dict(value.user_functionality or {}),
        'admin_visibility': dict(value.admin_visibility or {}),
        'measurable_outcome': value.outcome,
        'write_actions_enabled': False,
        'approval_required_before_execution': True,
        **_product_fields(value),
    }


def _cta_submit_response(result, owner_session: dict | None = None, owner_businesses=()) -> dict:
    payload = {**_base_response(result), 'next': {'ui_url': result.app_url}, 'owner_businesses': list(owner_businesses or ())}
    return {**payload, 'owner_session': owner_session} if owner_session else payload


def _cta_status_response(status_payload, owner_session: dict | None = None, owner_businesses=()) -> dict:
    if not status_payload.found:
        return {'ok': False, 'error': 'not_found', 'intake_id': status_payload.intake_id}
    payload = {**_base_response(status_payload), 'found': True, 'owner_businesses': list(owner_businesses or ())}
    return {**payload, 'owner_session': owner_session} if owner_session else payload


def _owner_session_payload(record, raw_key: str, *, tenant_id: str, business_id: str) -> dict[str, object]:
    return {
        'api_key': raw_key,
        'tenant_id': tenant_id,
        'business_id': business_id,
        'expires_at': None if record.expires_at is None else record.expires_at.isoformat(),
        'storage': 'session_only',
    }


def _owner_display_name(value) -> str | None:
    return str((getattr(value, 'business_profile', None) or {}).get('name') or '').strip() or None


def _set_cookie(*, response: Response, request: Request, key: str, raw_key: str, max_age: int) -> None:
    response.set_cookie(
        key=key,
        value=raw_key,
        max_age=max_age,
        httponly=True,
        secure=str(request.url.scheme).lower() == 'https',
        samesite='strict',
        path='/',
    )


def _set_owner_resume_cookie(*, response: Response, request: Request, raw_key: str) -> None:
    _set_cookie(response=response, request=request, key=_OWNER_RESUME_COOKIE, raw_key=raw_key, max_age=_OWNER_RESUME_TTL_SECONDS)


def _set_owner_account_cookie(*, response: Response, request: Request, raw_key: str) -> None:
    _set_cookie(response=response, request=request, key=_OWNER_ACCOUNT_COOKIE, raw_key=raw_key, max_age=_OWNER_ACCOUNT_TTL_SECONDS)


def _owner_account_identity(*, request: Request, policy):
    raw_key = str(request.cookies.get(_OWNER_ACCOUNT_COOKIE) or '').strip()
    return (raw_key, policy.resolve_owner_account_session(resume_key=raw_key)) if policy is not None and raw_key else ('', None)


def _refresh_owner_account_cookie_if_needed(*, response: Response, request: Request, policy, raw_key: str, owner_account_id: str, subject: str, tenant_id: str, display_name: str | None) -> None:
    if not raw_key or not policy.owner_account_session_needs_refresh(resume_key=raw_key):
        return
    _, refreshed = policy.issue_owner_account_session(
        tenant_id=tenant_id,
        owner_account_id=owner_account_id,
        subject=subject,
        display_name=display_name,
        ttl_seconds=_OWNER_ACCOUNT_TTL_SECONDS,
    )
    _set_owner_account_cookie(response=response, request=request, raw_key=refreshed)


def register_public_site_routes(*, router, enforce_public_security, auth_bundle=None, tenant_registry=None) -> None:
    service = CTALandingIntakeService()

    def secure(request: Request, route: str, body: dict) -> None:
        enforce_public_security(
            route_path=route,
            request_context=RequestContext.from_http_request(request, metadata={'route': route}),
            body=body,
            http_request=request,
        )

    def api_key_policy():
        return getattr(getattr(auth_bundle, 'auth_policy', None), 'api_key_policy', None)

    @router.get('/public-site/integrations', tags=['public-site'])
    async def public_site_integrations(http_request: Request) -> dict:
        secure(http_request, '/public-site/integrations', {})
        rows = public_integration_marketplace()
        return {
            'ok': True,
            'items': list(rows),
            'total': len(rows),
            'policy': {
                'initial_sync': 'read_only',
                'write_actions_enabled': False,
                'credential_activation_requires_authenticated_control_plane': True,
            },
        }

    @router.get('/public-site/owner/businesses', tags=['public-site'])
    async def public_site_owner_businesses(http_request: Request) -> dict:
        secure(http_request, '/public-site/owner/businesses', {})
        policy = api_key_policy()
        _, account = _owner_account_identity(request=http_request, policy=policy)
        if account is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='owner_account_session_required')
        owner_account_id, _ = account
        return {'ok': True, 'businesses': list(service.list_owner_businesses(owner_account_id=owner_account_id))}

    @router.post('/public-site/cta/start', tags=['public-site'])
    async def public_site_cta_start(http_request: Request, response: Response) -> dict:
        try:
            payload = await http_request.json()
        except Exception:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        secure(http_request, '/public-site/cta/start', payload)
        policy = api_key_policy()
        account_key, account = _owner_account_identity(request=http_request, policy=policy)
        account_id, owner_subject = account if account is not None else (None, None)
        result = service.submit(payload=payload, owner_account_id=account_id, owner_subject=owner_subject)
        owner_session, owner_businesses = None, ()
        if tenant_registry is not None and policy is not None:
            display_name = _owner_display_name(result)
            ensure_tenant_record(tenant_registry, result.tenant_id, display_name=display_name or result.tenant_id)
            record, raw_key = policy.issue_owner_session(
                tenant_id=result.tenant_id,
                business_id=result.business_id,
                subject=result.user_id,
                display_name=display_name,
            )
            _, raw_resume_key = policy.issue_owner_resume_session(
                tenant_id=result.tenant_id,
                business_id=result.business_id,
                intake_id=result.intake_id,
                subject=result.user_id,
                display_name=display_name,
                ttl_seconds=_OWNER_RESUME_TTL_SECONDS,
            )
            _set_owner_resume_cookie(response=response, request=http_request, raw_key=raw_resume_key)
            if account is None:
                _, account_key = policy.issue_owner_account_session(
                    tenant_id=result.tenant_id,
                    owner_account_id=result.owner_account_id,
                    subject=result.user_id,
                    display_name=display_name,
                    ttl_seconds=_OWNER_ACCOUNT_TTL_SECONDS,
                )
                _set_owner_account_cookie(response=response, request=http_request, raw_key=account_key)
            else:
                _refresh_owner_account_cookie_if_needed(
                    response=response, request=http_request, policy=policy, raw_key=account_key,
                    owner_account_id=result.owner_account_id, subject=result.user_id, tenant_id=result.tenant_id, display_name=display_name,
                )
            response.headers['Cache-Control'] = 'no-store'
            owner_session = _owner_session_payload(record, raw_key, tenant_id=result.tenant_id, business_id=result.business_id)
            owner_businesses = service.list_owner_businesses(owner_account_id=result.owner_account_id)
        return _cta_submit_response(result, owner_session, owner_businesses)

    @router.get('/public-site/cta/{intake_id}', tags=['public-site'])
    async def public_site_cta_status(http_request: Request, response: Response, intake_id: str) -> dict:
        secure(http_request, '/public-site/cta/{intake_id}', {'intake_id': intake_id})
        status_payload, owner_session, owner_businesses, policy = service.get_status(intake_id=intake_id), None, (), api_key_policy()
        if not status_payload.found or policy is None:
            return _cta_status_response(status_payload, owner_session, owner_businesses)

        account_key, account = _owner_account_identity(request=http_request, policy=policy)
        resumed = None
        if account is not None and account == (status_payload.owner_account_id, status_payload.user_id):
            display_name = _owner_display_name(status_payload)
            resumed = policy.resume_owner_account_business(
                resume_key=account_key,
                owner_account_id=status_payload.owner_account_id,
                subject=status_payload.user_id,
                tenant_id=status_payload.tenant_id,
                business_id=status_payload.business_id,
                display_name=display_name,
            )
            _refresh_owner_account_cookie_if_needed(
                response=response, request=http_request, policy=policy, raw_key=account_key,
                owner_account_id=status_payload.owner_account_id, subject=status_payload.user_id, tenant_id=status_payload.tenant_id, display_name=display_name,
            )
            owner_businesses = service.list_owner_businesses(owner_account_id=status_payload.owner_account_id)
        else:
            resume_key = str(http_request.cookies.get(_OWNER_RESUME_COOKIE) or '').strip()
            if resume_key:
                resumed = policy.resume_owner_session(
                    resume_key=resume_key,
                    intake_id=status_payload.intake_id,
                    tenant_id=status_payload.tenant_id,
                    business_id=status_payload.business_id,
                )
                if resumed is not None:
                    _, raw_account_key = policy.issue_owner_account_session(
                        tenant_id=status_payload.tenant_id,
                        owner_account_id=status_payload.owner_account_id,
                        subject=status_payload.user_id,
                        display_name=_owner_display_name(status_payload),
                        ttl_seconds=_OWNER_ACCOUNT_TTL_SECONDS,
                    )
                    _set_owner_account_cookie(response=response, request=http_request, raw_key=raw_account_key)
                    owner_businesses = service.list_owner_businesses(owner_account_id=status_payload.owner_account_id)
                else:
                    response.delete_cookie(key=_OWNER_RESUME_COOKIE, path='/', samesite='strict')

        if resumed is not None:
            record, raw_key = resumed
            response.headers['Cache-Control'] = 'no-store'
            owner_session = _owner_session_payload(record, raw_key, tenant_id=status_payload.tenant_id, business_id=status_payload.business_id)
        return _cta_status_response(status_payload, owner_session, owner_businesses)
