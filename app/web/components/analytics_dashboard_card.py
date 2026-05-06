from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_ANALYTICS_DASHBOARD_CARD = True


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class AnalyticsDashboardCard:
    kind: str = 'analytics_dashboard_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = _safe_dict(payload)
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(self.kind, {'tenant_id': tenant_id, 'overall_state': str(normalized.get('overall_state') or 'unknown'), 'overall_score': float(normalized.get('overall_score') or 0.0), 'window_days': int(normalized.get('window_days') or 30), 'sections': _safe_dict(normalized.get('sections')), 'highlights': tuple(normalized.get('highlights') or ()), 'risks': tuple(normalized.get('risks') or ())})
