from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_CAPACITY_BUDGET_PANEL = True


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class CapacityBudgetPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'capacity_budget_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        headroom_usd = max(0.0, _safe_float(normalized.get('headroom_usd')))
        burn_rate_usd_per_hour = max(0.0, _safe_float(normalized.get('burn_rate_usd_per_hour')))
        risk_level = 'high' if burn_rate_usd_per_hour > 50.0 else 'moderate' if burn_rate_usd_per_hour > 20.0 else 'low'
        result = {
            'tenant_id': tenant_id,
            'title': 'Inference Capacity Budget',
            'headroom_usd': round(headroom_usd, 6),
            'burn_rate_usd_per_hour': round(burn_rate_usd_per_hour, 6),
            'risk_level': risk_level,
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
