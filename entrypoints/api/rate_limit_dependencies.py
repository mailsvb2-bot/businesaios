from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from tenancy.tenant_quota_guard import TenantQuotaGuard


CANON_API_RATE_LIMIT_DEPENDENCIES = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class RateLimitDependencyBundle:
    tenant_quota_guard: TenantQuotaGuard

    def require_quota(
        self,
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        dimension: str,
        amount: float = 1.0,
    ) -> None:
        if not str(dimension or '').strip():
            raise ValueError('dimension is required')
        tenant_id = principal.tenant_id or request_context.validated_tenant_id(required=True)
        verdict = self.tenant_quota_guard.consume(
            tenant_id=tenant_id,
            dimension=dimension,
            amount=amount,
        )
        if not verdict.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    'reason': verdict.reason,
                    'dimension': verdict.dimension,
                    'tenant_id': verdict.tenant_id,
                    'remaining': verdict.remaining,
                },
                headers={
                    'Retry-After': str(verdict.retry_after_seconds or 60),
                },
            )


__all__ = [
    'CANON_API_RATE_LIMIT_DEPENDENCIES',
    'RateLimitDependencyBundle',
]
