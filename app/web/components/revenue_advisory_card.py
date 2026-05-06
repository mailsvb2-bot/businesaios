from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_REVENUE_ADVISORY_CARD = True


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class RevenueAdvisoryCard:
    kind: str = 'revenue_advisory_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        flags = normalized.get('flags')
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'product_id': str(normalized.get('product_id') or ''),
                'generated_at': str(normalized.get('generated_at') or ''),
                'projected_ltv': _safe_float(normalized.get('projected_ltv')),
                'projected_churn_rate': _safe_float(normalized.get('projected_churn_rate')),
                'recommended_price_plan_id': normalized.get('recommended_price_plan_id'),
                'recommended_price_amount': None if normalized.get('recommended_price_amount') is None else _safe_float(normalized.get('recommended_price_amount')),
                'recommended_paywall_variant_id': normalized.get('recommended_paywall_variant_id'),
                'recommended_subscription_plan_id': normalized.get('recommended_subscription_plan_id'),
                'highest_blast_radius': str(normalized.get('highest_blast_radius') or 'low'),
                'approval_required_count': _safe_int(normalized.get('approval_required_count')),
                'experiments_count': _safe_int(normalized.get('experiments_count')),
                'action_mappings_count': _safe_int(normalized.get('action_mappings_count')),
                'flags': dict(flags) if isinstance(flags, Mapping) else {},
                'tenant_bound': True,
            },
        )


__all__ = ['CANON_WEB_REVENUE_ADVISORY_CARD', 'RevenueAdvisoryCard']
