from __future__ import annotations

"""Final owner: adapters.api.fastapi.router_support."""

import json
from typing import Any

from fastapi import HTTPException, Request, status

from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
from config.env_flags import env_bool, env_str
from entrypoints.api.api_key_policy import ApiKeyPolicy, build_default_api_key_store
from entrypoints.api.jwt_policy import JwtPolicy
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from governance.rbac_contract import RoleId
from observability.metrics import InMemoryMetrics
from security.key_provider import build_default_key_provider
from security.webhook_signature_verifier import WebhookSignatureVerifier


CANON_FASTAPI_ROUTER_SUPPORT_FINAL_OWNER = True


def authorize_request(*, request: Request, auth_bundle: AuthDependencyBundle):
    untrusted_context = RequestContext.from_http_request(request)
    principal = auth_bundle.authenticate(
        request=request,
        request_context=untrusted_context,
        authorization=request.headers.get('Authorization'),
        x_api_key=request.headers.get('X-API-Key'),
    )
    principal_tenant = str(principal.tenant_id or '').strip()
    if not principal_tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='authenticated_principal_tenant_required')
    principal_actor = str(principal.actor_id or principal.subject or '').strip()
    if not principal_actor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='authenticated_principal_actor_required')

    auth_type = str(principal.metadata.get('auth_type') or '').strip().lower()
    proof = {
        'auth_level': auth_type or 'authenticated',
        'authenticated_principal': True,
        'principal_roles': tuple(role.value for role in principal.roles),
    }
    if auth_type == 'api_key':
        proof['api_key_verified'] = True
    elif auth_type == 'jwt':
        proof['jwt_verified'] = True

    request_context = RequestContext(
        request_id=untrusted_context.request_id,
        correlation_id=untrusted_context.correlation_id,
        tenant_id=principal_tenant,
        actor_id=principal_actor,
        session_id=principal.session_id,
        subject=principal.subject,
        audience=principal.audience,
        ip_address=untrusted_context.ip_address,
        user_agent=untrusted_context.user_agent,
        token_scopes=tuple(principal.scopes),
        metadata={**dict(untrusted_context.metadata), **proof},
    )
    return request_context, principal


def business_owner_scope(*, request: Request, auth_bundle: AuthDependencyBundle, required_scope: str | None = None):
    _, principal = authorize_request(request=request, auth_bundle=auth_bundle)
    if RoleId.OWNER not in tuple(principal.roles) or (required_scope and required_scope not in tuple(principal.scopes)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='owner_business_scope_required')
    tenant_id = str(principal.tenant_id or '').strip()
    business_id = str(dict(principal.metadata or {}).get('business_id') or '').strip()
    if not tenant_id or not business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='business_workspace_scope_missing')
    return principal, tenant_id, business_id


def tenant_if_present(*, principal, request_context, tenant_guard, body):
    has_any_tenant = bool(principal.tenant_id or request_context.tenant_id or (body or {}).get('tenant_id'))
    if has_any_tenant:
        return tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
    return None


async def json_body(request: Request) -> dict[str, Any]:
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        return {}
    raw = await request.body()
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode('utf-8'))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='invalid_json_body') from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='json_body_must_be_object')
    return payload


def first_role(principal):
    if not principal.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='authenticated_principal_role_required')
    return principal.roles[0]


def normalized_env_name() -> str:
    return (env_str('APP_ENV', env_str('ENV', 'dev')) or 'dev').strip().lower()


def is_production_env_name(env_name: str) -> bool:
    return str(env_name or '').strip().lower() in {'prod', 'production'}


def enforce_control_plane_auth_prod_contract(*, env_name: str, pepper: str) -> None:
    if not is_production_env_name(env_name):
        return
    if not str(pepper or '').strip():
        raise RuntimeError('PRODUCTION_CONTROL_PLANE_API_KEY_PEPPER_REQUIRED')
    backend = env_str('BUSINESAIOS_API_KEY_STORE_BACKEND', 'file').strip().lower()
    if backend == 'memory':
        raise RuntimeError('PRODUCTION_CONTROL_PLANE_API_KEY_STORE_MUST_BE_PERSISTENT')
    if not env_str('BUSINESAIOS_API_KEY_STORE_PATH', '').strip():
        raise RuntimeError('PRODUCTION_CONTROL_PLANE_API_KEY_STORE_PATH_REQUIRED')


def build_auth_bundle(*, security_bundle: ApiSecurityOwnerBundle) -> AuthDependencyBundle:
    env_name = normalized_env_name()
    jwt_secret = env_str('API_CONTROL_PLANE_JWT_SECRET', '').strip()
    jwt_audience = env_str('API_CONTROL_PLANE_JWT_AUDIENCE', 'control-plane').strip() or 'control-plane'
    jwt_issuer = env_str('API_CONTROL_PLANE_JWT_ISSUER', 'businesaios-api').strip() or 'businesaios-api'
    allow_dev_fallbacks = env_bool('API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS', not is_production_env_name(env_name))
    dev_jwt_secret = env_str('API_CONTROL_PLANE_DEV_JWT_SECRET', '').strip()
    jwt_policy = None
    if jwt_secret:
        jwt_policy = JwtPolicy(secret=jwt_secret, audience=jwt_audience, issuer=jwt_issuer)
    elif allow_dev_fallbacks and dev_jwt_secret:
        jwt_policy = JwtPolicy(secret=dev_jwt_secret, audience=jwt_audience, issuer=jwt_issuer)

    pepper = env_str('API_CONTROL_PLANE_API_KEY_PEPPER', '').strip()
    if not pepper and allow_dev_fallbacks:
        pepper = env_str('API_CONTROL_PLANE_DEV_API_KEY_PEPPER', '').strip()
    enforce_control_plane_auth_prod_contract(env_name=env_name, pepper=pepper)
    api_key_policy = ApiKeyPolicy(store=build_default_api_key_store(pepper=pepper))
    return AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(
            api_key_policy=api_key_policy,
            jwt_policy=jwt_policy,
            allow_anonymous=False,
            allow_multiple_mechanisms=False,
        ),
        security_guard=security_bundle.api_surface_guard,
    )


def build_webhook_verifier() -> WebhookSignatureVerifier:
    return WebhookSignatureVerifier(
        key_provider=build_default_key_provider(),
        require_timestamp=True,
        require_nonce=True,
    )


def resolve_metrics(*, dependency_container: FastAPIDependencyContainer | None) -> InMemoryMetrics:
    if dependency_container is not None:
        metrics = dependency_container.metrics()
        if isinstance(metrics, InMemoryMetrics):
            return metrics
    return InMemoryMetrics()


def tenant_registry_has_records(registry: object) -> bool:
    return bool(getattr(registry, '_records', {}))
