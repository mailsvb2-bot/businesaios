from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_MONETIZATION_DASHBOARD_CARD = True


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class MonetizationDashboardCard:
    kind: str = 'monetization_dashboard_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        gross = _safe_int(normalized.get('gross_revenue_minor'))
        refunded = _safe_int(normalized.get('refunded_minor'))
        chargeback = _safe_int(normalized.get('chargeback_minor'))
        net = _safe_int(normalized.get('net_revenue_minor', gross - refunded - chargeback))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'gross_revenue_minor': gross,
                'refunded_minor': refunded,
                'chargeback_minor': chargeback,
                'net_revenue_minor': net,
                'active_subscriptions': _safe_int(normalized.get('active_subscriptions')),
                'past_due_subscriptions': _safe_int(normalized.get('past_due_subscriptions')),
                'cancelled_subscriptions': _safe_int(normalized.get('cancelled_subscriptions')),
                'currency': str(normalized.get('currency') or 'USD').upper(),
                'tenant_bound': True,
            },
        )


__all__ = ['CANON_WEB_MONETIZATION_DASHBOARD_CARD', 'MonetizationDashboardCard']
