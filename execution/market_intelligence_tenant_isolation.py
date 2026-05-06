from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_TENANT_ISOLATION = True


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(frozen=True)
class TenantIntelligenceScope:
    tenant_id: str
    allowed_providers: tuple[str, ...] = field(default_factory=tuple)
    allowed_source_families: tuple[str, ...] = field(default_factory=tuple)
    max_records_per_sync: int = 100
    memory_partition: str | None = None

    def allows(self, *, provider: str, source_family: str) -> bool:
        if self.allowed_providers and str(provider) not in set(self.allowed_providers):
            return False
        if self.allowed_source_families and str(source_family) not in set(self.allowed_source_families):
            return False
        return True


class TenantIsolationGuard:
    def enforce(self, request_payload: Mapping[str, Any], scope: TenantIntelligenceScope) -> dict[str, Any]:
        payload = _safe_dict(request_payload)
        provider = str(payload.get('provider') or '').strip()
        source_family = str(payload.get('source_family') or '').strip()
        if str(payload.get('tenant_id') or '').strip() != str(scope.tenant_id):
            raise ValueError('tenant mismatch')
        if not scope.allows(provider=provider, source_family=source_family):
            raise PermissionError('tenant scope does not allow provider/source_family')
        limit = int(payload.get('limit') or scope.max_records_per_sync)
        payload['limit'] = max(1, min(limit, int(scope.max_records_per_sync)))
        payload['memory_partition'] = str(scope.memory_partition or scope.tenant_id)
        return payload


__all__ = ['CANON_MARKET_INTELLIGENCE_TENANT_ISOLATION', 'TenantIsolationGuard', 'TenantIntelligenceScope']
