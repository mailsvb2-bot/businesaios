from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_CLIENT_OUTCOME_DASHBOARD_CARD = True


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
class ClientOutcomeDashboardCard:
    kind: str = 'client_outcome_dashboard_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'requested_clients': _safe_int(normalized.get('requested_clients')),
                'billable_clients': _safe_int(normalized.get('billable_clients')),
                'reversed_clients': _safe_int(normalized.get('reversed_clients')),
                'open_disputes': _safe_int(normalized.get('open_disputes')),
                'gross_revenue': _safe_float(normalized.get('gross_revenue')),
                'net_revenue': _safe_float(normalized.get('net_revenue')),
                'currency': str(normalized.get('currency') or 'EUR').upper(),
                'tenant_bound': True,
            },
        )
