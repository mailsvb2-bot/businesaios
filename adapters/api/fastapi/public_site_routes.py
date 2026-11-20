from __future__ import annotations

from fastapi import HTTPException, Request, Response, status

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace
from entrypoints.api.request_context import RequestContext
from tenancy.tenant_registry import ensure_tenant_record

ORGANIZATION_OWNED_FIELDS = ("business_name", "organization_type")
SETTINGS_OWNED_FIELDS = ("activity_description", "timezone_name")
NAME_MIGRATION_VERSION = "intake_business_name_v1"


def canonical_organization_name_enabled() -> bool:
    from config.env_flags import env_bool

    return env_bool("BAI_UNIFIED_ORGANIZATION_SETTINGS_ENABLED", False) and env_bool(
        "BAI_ORGANIZATION_NAME_CANONICAL_ENABLED", False
    )


def _canonical_name_read(registry, *, tenant_id: str, business_id: str, settings: dict) -> dict:
    from application.organization.registry import business_organization

    org = business_organization(registry, tenant_id=tenant_id, business_id=business_id)
    if org is None:
        return {**settings, "name_source": "intake_pending_migration",
                "organization_updated_at_ms": None}
    return {**settings, "business_name": org.name or settings["business_name"],
            "name_source": "application.organization.registry",
            "organization_updated_at_ms": org.updated_at_ms}


def _canonical_name_write(registry, *, tenant_id: str, business_id: str,
                          original_name: str, requested_name: str, key: str, actor: str):
    from application.organization.registry import business_organization

    identity = {"tenant_id": tenant_id, "business_id": business_id, "organization_id": business_id}
    org = business_organization(registry, tenant_id=tenant_id, business_id=business_id)
    if org is None:
        org = registry.create(**identity, idempotency_key=f"org-migration:{NAME_MIGRATION_VERSION}:{business_id}",
                              name=original_name, event_metadata={"actor_id": "system:migration",
                              "provenance": {"migration": NAME_MIGRATION_VERSION}})
    if org.name != requested_name:
        org = registry.update(**identity, idempotency_key=f"web-settings:{key}",
                              name=requested_name, event_metadata={"actor_id": actor})
    return org


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
    response.set_cookie( key=key, value=raw_key, max_age=max_age, httponly=True, secure=str(request.url.scheme).lower() == 'https',
        samesite='strict', path='/', )


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
    _, refreshed = policy.issue_owner_account_session( tenant_id=tenant_id, owner_account_id=owner_account_id, subject=subject,
        display_name=display_name, ttl_seconds=_OWNER_ACCOUNT_TTL_SECONDS, )
    _set_owner_account_cookie(response=response, request=request, raw_key=refreshed)


def register_public_site_routes(*, router, enforce_public_security, auth_bundle=None, tenant_registry=None,
                                event_landing_registry=None, organization_registry=None) -> None:
    service = CTALandingIntakeService()

    def secure(request: Request, route: str, body: dict) -> None:
        enforce_public_security( route_path=route, request_context=RequestContext.from_http_request(request,
        metadata={'route': route}), body=body, http_request=request, )

    def api_key_policy():
        return getattr(getattr(auth_bundle, 'auth_policy', None), 'api_key_policy', None)

    @router.get('/business-workspace/settings', tags=['business-workspace'])
    async def owner_business_settings(http_request: Request) -> dict:
        _, tenant_id, business_id = business_owner_scope( request=http_request, auth_bundle=auth_bundle,
        required_scope='provider_control_plane', )
        try:
            settings = service.read_business_settings(tenant_id=tenant_id, business_id=business_id)
            if canonical_organization_name_enabled():
                if organization_registry is None:
                    raise HTTPException(status_code=503, detail="organization_owner_unavailable")
                return _canonical_name_read(organization_registry, tenant_id=tenant_id,
                                            business_id=business_id, settings=settings)
            return settings
        except KeyError as exc:
            raise HTTPException(status_code=404, detail='business_settings_not_found') from exc

    @router.post('/business-workspace/settings', tags=['business-workspace'])
    async def save_owner_business_settings(http_request: Request) -> dict:
        principal, tenant_id, business_id = business_owner_scope( request=http_request, auth_bundle=auth_bundle,
        required_scope='provider_control_plane', )
        body = await json_body(http_request)
        required = {'business_name', 'activity_description', 'timezone_name', 'expected_revision'}
        canonical = canonical_organization_name_enabled()
        permitted = required | ({"expected_organization_updated_at_ms"} if canonical else set())
        if not isinstance(body, dict) or set(body) - permitted or not required <= set(body):
            raise HTTPException(status_code=422, detail='business_settings_fields_invalid')
        if canonical and organization_registry is None:
            raise HTTPException(status_code=503, detail="organization_owner_unavailable")
        key = str(http_request.headers.get('x-idempotency-key') or '').strip()
        if not key or len(key) > 200:
            raise HTTPException(status_code=422, detail='business_settings_idempotency_key_required')
        try:
            actor = str(getattr(principal, "actor_id", None) or getattr(principal, "subject", "") or "")
            if canonical:
                from application.organization.registry import business_organization

                original = service.read_business_settings(tenant_id=tenant_id, business_id=business_id)
                org = business_organization(organization_registry, tenant_id=tenant_id, business_id=business_id)
                expected_org = body.get("expected_organization_updated_at_ms")
                new_name = str(body["business_name"] or "").strip()
                if not 1 <= len(new_name) <= 200:
                    raise ValueError("business_settings_fields_invalid")
                if (org is not None and org.name != new_name
                        and (expected_org is None or isinstance(expected_org, bool)
                             or not isinstance(expected_org, int) or expected_org != org.updated_at_ms)):
                    raise RuntimeError("business_settings_stale_revision")
                # An idempotent intake receipt survives a partially completed
                # Organization update. Retrying the SAME key resumes the latter.
                saved = service.update_business_settings(
                    tenant_id=tenant_id, business_id=business_id, business_name=None,
                    activity_description=body["activity_description"], timezone_name=body["timezone_name"],
                    expected_revision=body["expected_revision"], idempotency_key=key, actor_id=actor,
                )
                updated = _canonical_name_write(
                    organization_registry, tenant_id=tenant_id, business_id=business_id,
                    original_name=str(original["business_name"] or "").strip(), requested_name=new_name,
                    key=key, actor=actor,
                )
                return {**saved, "business_name": updated.name, "name_source": "application.organization.registry",
                        "organization_updated_at_ms": updated.updated_at_ms}
            return service.update_business_settings(
                tenant_id=tenant_id, business_id=business_id,
                business_name=body["business_name"], activity_description=body["activity_description"],
                timezone_name=body["timezone_name"], expected_revision=body["expected_revision"],
                idempotency_key=key, actor_id=actor,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail='business_settings_not_found') from exc
        except ValueError as exc:
            if str(exc) == 'business_settings_idempotency_conflict':
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            if str(exc) == 'business_settings_stale_revision':
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise

    @router.get('/public-site/events/{tenant_id}/{business_id}/{event_id}', tags=['public-site'])
    async def public_event_landing(tenant_id: str, business_id: str, event_id: str, http_request: Request) -> dict:
        secure(http_request, '/public-site/events/{tenant_id}/{business_id}/{event_id}', {'tenant_id': tenant_id, 'business_id': business_id, 'event_id': event_id})
        if event_landing_registry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='event_landing_not_found')
        try:
            state = event_landing_registry.get(tenant_id=tenant_id, business_id=business_id, event_id=event_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='event_landing_not_found') from exc
        published = state.public_content()
        if published is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='event_landing_not_published')
        return {'ok': True, 'event_id': event_id, 'revision': state.published_revision, 'content': published.to_payload()}

    @router.post('/public-site/events/{tenant_id}/{business_id}/{event_id}/registrations', tags=['public-site'])
    async def public_event_registration(tenant_id: str, business_id: str, event_id: str, http_request: Request) -> dict:
        # Public security sees the scope, never the raw participant email.
        secure(http_request, '/public-site/events/{tenant_id}/{business_id}/{event_id}',
               {'tenant_id': tenant_id, 'business_id': business_id, 'event_id': event_id})
        if event_landing_registry is None:
            raise HTTPException(status_code=404, detail='event_landing_not_found')
        body = await json_body(http_request)
        if set(body) != {'email', 'consent'}:
            raise HTTPException(status_code=422, detail='registration_fields_invalid')
        key = str(http_request.headers.get('x-idempotency-key') or '').strip()
        try:
            return event_landing_registry.register( tenant_id=tenant_id, business_id=business_id, event_id=event_id, email=body['email'],
        consent=body['consent'], idempotency_key=key, )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail='event_landing_not_found') from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
            record, raw_key = policy.issue_owner_session( tenant_id=result.tenant_id, business_id=result.business_id,
        subject=result.user_id, display_name=display_name, )
            _, raw_resume_key = policy.issue_owner_resume_session( tenant_id=result.tenant_id, business_id=result.business_id, intake_id=result.intake_id, subject=result.user_id,
        display_name=display_name, ttl_seconds=_OWNER_RESUME_TTL_SECONDS, )
            _set_owner_resume_cookie(response=response, request=http_request, raw_key=raw_resume_key)
            if account is None:
                _, account_key = policy.issue_owner_account_session( tenant_id=result.tenant_id, owner_account_id=result.owner_account_id, subject=result.user_id,
        display_name=display_name, ttl_seconds=_OWNER_ACCOUNT_TTL_SECONDS, )
                _set_owner_account_cookie(response=response, request=http_request, raw_key=account_key)
            else:
                _refresh_owner_account_cookie_if_needed( response=response, request=http_request, policy=policy, raw_key=account_key, owner_account_id=result.owner_account_id,
        subject=result.user_id, tenant_id=result.tenant_id, display_name=display_name, )
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
            resumed = policy.resume_owner_account_business( resume_key=account_key, owner_account_id=status_payload.owner_account_id, subject=status_payload.user_id,
        tenant_id=status_payload.tenant_id, business_id=status_payload.business_id, display_name=display_name, )
            _refresh_owner_account_cookie_if_needed( response=response, request=http_request, policy=policy, raw_key=account_key, owner_account_id=status_payload.owner_account_id,
        subject=status_payload.user_id, tenant_id=status_payload.tenant_id, display_name=display_name, )
            owner_businesses = service.list_owner_businesses(owner_account_id=status_payload.owner_account_id)
        else:
            resume_key = str(http_request.cookies.get(_OWNER_RESUME_COOKIE) or '').strip()
            if resume_key:
                resumed = policy.resume_owner_session( resume_key=resume_key, intake_id=status_payload.intake_id, tenant_id=status_payload.tenant_id,
        business_id=status_payload.business_id, )
                if resumed is not None:
                    _, raw_account_key = policy.issue_owner_account_session( tenant_id=status_payload.tenant_id, owner_account_id=status_payload.owner_account_id, subject=status_payload.user_id,
        display_name=_owner_display_name(status_payload), ttl_seconds=_OWNER_ACCOUNT_TTL_SECONDS, )
                    _set_owner_account_cookie(response=response, request=http_request, raw_key=raw_account_key)
                    owner_businesses = service.list_owner_businesses(owner_account_id=status_payload.owner_account_id)
                else:
                    response.delete_cookie(key=_OWNER_RESUME_COOKIE, path='/', samesite='strict')

        if resumed is not None:
            record, raw_key = resumed
            response.headers['Cache-Control'] = 'no-store'
            owner_session = _owner_session_payload(record, raw_key, tenant_id=status_payload.tenant_id, business_id=status_payload.business_id)
        return _cta_status_response(status_payload, owner_session, owner_businesses)
