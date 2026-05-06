from __future__ import annotations

"""Final owner: adapters.api.fastapi.router_support."""

CANON_FASTAPI_ROUTER_SUPPORT_FINAL_OWNER = True


import json
from typing import Any

from fastapi import HTTPException, Request, status

from config.env_flags import env_bool, env_str
from entrypoints.api.api_key_policy import ApiKeyPolicy, build_default_api_key_store
from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
from entrypoints.api.jwt_policy import JwtPolicy
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from observability.metrics import InMemoryMetrics
from security.key_management_contract import KeyPurpose
from security.key_provider import build_default_key_provider
from security.webhook_signature_verifier import WebhookSignatureVerifier


def authorize_request(*, request: Request, auth_bundle: AuthDependencyBundle):
    request_context = RequestContext.from_http_request(request)
    principal = auth_bundle.authenticate(
        request=request,
        request_context=request_context,
        authorization=request.headers.get('Authorization'),
        x_api_key=request.headers.get('X-API-Key'),
    )
    return request_context, principal


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
    if principal.roles:
        return principal.roles[0]
    from governance.rbac_contract import RoleId
    return RoleId.OWNER


def normalized_env_name() -> str:
    return (env_str('APP_ENV', env_str('ENV', 'dev')) or 'dev').strip().lower()


def build_auth_bundle(*, security_bundle: ApiSecurityOwnerBundle) -> AuthDependencyBundle:
    env_name = normalized_env_name()
    jwt_secret = env_str('API_CONTROL_PLANE_JWT_SECRET', '').strip()
    jwt_audience = env_str('API_CONTROL_PLANE_JWT_AUDIENCE', 'control-plane').strip() or 'control-plane'
    jwt_issuer = env_str('API_CONTROL_PLANE_JWT_ISSUER', 'businesaios-api').strip() or 'businesaios-api'
    allow_dev_fallbacks = env_bool('API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS', env_name != 'prod')
    dev_jwt_secret = env_str('API_CONTROL_PLANE_DEV_JWT_SECRET', '').strip()
    jwt_policy = None
    if jwt_secret:
        jwt_policy = JwtPolicy(secret=jwt_secret, audience=jwt_audience, issuer=jwt_issuer)
    elif allow_dev_fallbacks and dev_jwt_secret:
        jwt_policy = JwtPolicy(secret=dev_jwt_secret, audience=jwt_audience, issuer=jwt_issuer)

    pepper = env_str('API_CONTROL_PLANE_API_KEY_PEPPER', '').strip()
    if not pepper and allow_dev_fallbacks:
        pepper = env_str('API_CONTROL_PLANE_DEV_API_KEY_PEPPER', '').strip()
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
    provider = build_default_key_provider()
    default_key_id = env_str('API_CONTROL_PLANE_WEBHOOK_KEY_ID', 'webhook-global-v1').strip() or 'webhook-global-v1'
    try:
        provider.get(str(default_key_id))
    except Exception:
        provider.issue_key(key_id=default_key_id, purpose=KeyPurpose.WEBHOOK_VERIFICATION)
    return WebhookSignatureVerifier(key_provider=provider, require_timestamp=True)


def resolve_metrics(*, dependency_container: FastAPIDependencyContainer | None) -> InMemoryMetrics:
    if dependency_container is not None:
        metrics = dependency_container.metrics()
        if isinstance(metrics, InMemoryMetrics):
            return metrics
    return InMemoryMetrics()


def tenant_registry_has_records(registry: object) -> bool:
    return bool(getattr(registry, '_records', {}))
