from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, Request, status

from security.access_policy import SecurityAction

from entrypoints.api.api_key_policy import ApiKeyPolicy
from entrypoints.api.auth_contract import AuthPrincipal, AuthVerdict, RequestAuthentication
from entrypoints.api.jwt_policy import JwtPolicy
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard


CANON_API_AUTH_DEPENDENCIES = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class CompositeAuthPolicy:
    api_key_policy: ApiKeyPolicy | None = None
    jwt_policy: JwtPolicy | None = None
    allow_anonymous: bool = False
    allow_multiple_mechanisms: bool = False

    def authenticate(self, request: RequestAuthentication) -> AuthVerdict:
        request.validate()
        has_api_key = bool(str(request.api_key or '').strip())
        has_authorization = bool(str(request.authorization or '').strip())
        if has_api_key and has_authorization and not self.allow_multiple_mechanisms:
            verdict = AuthVerdict(allowed=False, reason='ambiguous_authentication_mechanisms', challenge='Bearer')
            verdict.validate()
            return verdict
        if has_api_key and self.api_key_policy is not None:
            verdict = self.api_key_policy.authenticate(request)
            verdict.validate()
            if verdict.allowed:
                return verdict
            if not has_authorization:
                return verdict
        if has_authorization and self.jwt_policy is not None:
            verdict = self.jwt_policy.authenticate(request)
            verdict.validate()
            if verdict.allowed:
                return verdict
            if not has_api_key:
                return verdict
        if self.allow_anonymous:
            principal = AuthPrincipal(subject='anonymous', metadata={'auth_type': 'anonymous'})
            verdict = AuthVerdict(allowed=True, reason='anonymous_allowed', principal=principal)
            verdict.validate()
            return verdict
        verdict = AuthVerdict(allowed=False, reason='missing_authentication', challenge='Bearer')
        verdict.validate()
        return verdict


@dataclass(frozen=True)
class AuthDependencyBundle:
    auth_policy: CompositeAuthPolicy
    security_guard: ApiSecuritySurfaceGuard

    def authenticate(
        self,
        *,
        request: Request,
        request_context: RequestContext,
        authorization: str | None,
        x_api_key: str | None,
    ) -> AuthPrincipal:
        verdict = self.auth_policy.authenticate(
            RequestAuthentication(
                tenant_id=request_context.validated_tenant_id(required=False),
                authorization=authorization,
                api_key=x_api_key,
                request_id=request_context.normalized_request_id(),
                correlation_id=request_context.normalized_correlation_id(),
                remote_ip=request_context.ip_address,
                user_agent=request_context.user_agent,
                extra_headers={str(k): str(v) for k, v in request.headers.items()},
            )
        )
        verdict.validate()
        if not verdict.allowed:
            headers = {'WWW-Authenticate': verdict.challenge or 'Bearer'} if verdict.challenge else None
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=verdict.reason, headers=headers)
        assert verdict.principal is not None
        try:
            self.security_guard.enforce(
                principal=verdict.principal,
                request_context=request_context,
                resource_type='api_authentication',
                resource_id=f"{request.method}:{request.url.path}",
                action=SecurityAction.READ,
                surface='api_authentication',
                audit_payload={'method': request.method, 'path': request.url.path},
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return verdict.principal


async def build_request_context(request: Request) -> RequestContext:
    return RequestContext.from_http_request(request)


async def require_authenticated_principal(
    request: Request,
    request_context: RequestContext,
    bundle: AuthDependencyBundle,
    authorization: str | None = Header(default=None, alias='Authorization'),
    x_api_key: str | None = Header(default=None, alias='X-API-Key'),
) -> AuthPrincipal:
    return bundle.authenticate(
        request=request,
        request_context=request_context,
        authorization=authorization,
        x_api_key=x_api_key,
    )


__all__ = [
    'AuthDependencyBundle',
    'CANON_API_AUTH_DEPENDENCIES',
    'CompositeAuthPolicy',
    'build_request_context',
    'require_authenticated_principal',
]
