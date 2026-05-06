from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from advisory.revenue_os.contracts import _required_text

CANON_ADVISORY_REVENUE_OS_TENANT_POLICY = True


@dataclass(frozen=True, slots=True)
class TenantRevenuePolicy:
    tenant_id: str
    pricing_enabled: bool = True
    paywall_enabled: bool = True
    subscriptions_enabled: bool = True
    experiments_enabled: bool = True
    max_daily_exposure_override: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def normalized_copy(self) -> 'TenantRevenuePolicy':
        override = self.max_daily_exposure_override
        if override is not None and int(override) <= 0:
            raise ValueError('max_daily_exposure_override must be > 0 when provided')
        return TenantRevenuePolicy(
            tenant_id=_required_text(self.tenant_id, field_name='tenant_id'),
            pricing_enabled=bool(self.pricing_enabled),
            paywall_enabled=bool(self.paywall_enabled),
            subscriptions_enabled=bool(self.subscriptions_enabled),
            experiments_enabled=bool(self.experiments_enabled),
            max_daily_exposure_override=None if override is None else int(override),
            metadata=dict(self.metadata),
        )


class TenantRevenuePolicyStore:
    def __init__(self, policies: Mapping[str, TenantRevenuePolicy] | None = None) -> None:
        self._policies = {
            str(key): value.normalized_copy() for key, value in dict(policies or {}).items()
        }

    def get(self, tenant_id: str) -> TenantRevenuePolicy:
        normalized_tenant_id = _required_text(tenant_id, field_name='tenant_id')
        existing = self._policies.get(normalized_tenant_id)
        if existing is not None:
            return existing
        return TenantRevenuePolicy(tenant_id=normalized_tenant_id).normalized_copy()


__all__ = ['CANON_ADVISORY_REVENUE_OS_TENANT_POLICY', 'TenantRevenuePolicy', 'TenantRevenuePolicyStore']
