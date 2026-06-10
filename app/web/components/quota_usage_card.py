from __future__ import annotations

"""Quota usage card for tenant runtime/admin surfaces."""

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUOTA_USAGE_CARD = True


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class QuotaUsageCard:
    kind: str = 'quota_usage_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        usage = {str(k): v for k, v in dict(normalized.get('usage', {}) or {}).items()}
        limits = {str(k): v for k, v in dict(normalized.get('limits', {}) or {}).items()}
        rows = []
        for dimension in sorted(set(usage) | set(limits)):
            used = _safe_float(usage.get(dimension), default=0.0)
            limit_raw = limits.get(dimension)
            limit_value = None if limit_raw is None else _safe_float(limit_raw, default=0.0)
            remaining = None if limit_value is None else round(max(0.0, limit_value - used), 4)
            utilization = None if limit_value in (None, 0.0) else round((used / limit_value) * 100.0, 2)
            rows.append(
                {
                    'dimension': str(dimension),
                    'used': round(used, 4),
                    'limit': None if limit_value is None else round(limit_value, 4),
                    'remaining': remaining,
                    'utilization_pct': utilization,
                    'breached': bool(limit_value is not None and used > limit_value),
                }
            )
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'rows': tuple(rows),
                'breached': any(bool(row['breached']) for row in rows),
                'tracked_dimensions': len(rows),
                'tenant_bound': True,
            },
        )

    def build_from_snapshot(self, *, tenant_id: str, usage: Mapping[str, Any], limits: Mapping[str, Any]) -> dict[str, Any]:
        return self.build({'tenant_id': require_tenant_id(tenant_id), 'usage': dict(usage or {}), 'limits': dict(limits or {})})


__all__ = ['QuotaUsageCard', 'CANON_WEB_QUOTA_USAGE_CARD']
