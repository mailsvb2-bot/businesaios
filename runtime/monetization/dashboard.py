from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.monetization.contracts import MonetizationDashboardSnapshot

CANON_RUNTIME_MONETIZATION_DASHBOARD = True


@dataclass(frozen=True, slots=True)
class MonetizationDashboardPresenter:
    def build(self, snapshot: MonetizationDashboardSnapshot) -> dict[str, Any]:
        return {
            'tenant_id': snapshot.tenant_id,
            'gross_revenue_minor': int(snapshot.gross_revenue_minor),
            'refunded_minor': int(snapshot.refunded_minor),
            'chargeback_minor': int(snapshot.chargeback_minor),
            'net_revenue_minor': int(snapshot.net_revenue_minor),
            'active_subscriptions': int(snapshot.active_subscriptions),
            'past_due_subscriptions': int(snapshot.past_due_subscriptions),
            'cancelled_subscriptions': int(snapshot.cancelled_subscriptions),
            'currency': str(snapshot.currency),
        }


__all__ = ['CANON_RUNTIME_MONETIZATION_DASHBOARD', 'MonetizationDashboardPresenter']
