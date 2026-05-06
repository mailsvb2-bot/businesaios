from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_ANALYTICS_EXPLAINABILITY_CARD = True


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class AnalyticsExplainabilityCard:
    kind: str = 'analytics_explainability_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = _safe_dict(payload)
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(self.kind, {'tenant_id': tenant_id, 'trace_kind': str(normalized.get('trace_kind') or 'analytics'), 'reasons': tuple(normalized.get('reasons') or ()), 'evidence': _safe_dict(normalized.get('evidence'))})
