from __future__ import annotations

"""Queue health card for operator/admin views."""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUEUE_HEALTH_CARD = True

_STATUS_ORDER = {"critical": 0, "degraded": 1, "healthy": 2, "unknown": 3}


def _attr_or_key(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass(frozen=True, slots=True)
class QueueHealthCard:
    kind: str = 'queue_health_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = [dict(item or {}) for item in tuple(normalized.get('rows', ()) or ())]
        for row in rows:
            row['tenant_id'] = tenant_id
        rows.sort(
            key=lambda item: (
                _STATUS_ORDER.get(str(item.get('status') or 'unknown').strip(), 99),
                -int(item.get('pending_jobs') or 0),
                str(item.get('queue_name') or ''),
            )
        )
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'rows': tuple(rows),
                'queue_count': len(rows),
                'critical_count': sum(1 for row in rows if str(row.get('status') or '') == 'critical'),
                'degraded_count': sum(1 for row in rows if str(row.get('status') or '') == 'degraded'),
                'healthy_count': sum(1 for row in rows if str(row.get('status') or '') == 'healthy'),
                'backpressure_queue_count': sum(1 for row in rows if str(row.get('backpressure_reason') or '').strip() not in {'', 'normal'}),
                'starving_tenant_total': sum(int(row.get('starving_tenants') or 0) for row in rows),
                'tenant_bound': True,
                'approval_required_total': sum(int(row.get('approval_required_count') or 0) for row in rows),
                'stale_queue_count': sum(1 for row in rows if str(row.get('freshness_state') or '') == 'stale'),
                'aging_queue_count': sum(1 for row in rows if str(row.get('freshness_state') or '') == 'aging'),
            },
        )

    def build_from_reports(self, *, tenant_id: str, reports: Iterable[Any]) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        rows: list[dict[str, Any]] = []
        for report in reports:
            if str(_attr_or_key(report, 'tenant_id', '') or '').strip() != required_tenant_id:
                continue
            backpressure = _attr_or_key(report, 'backpressure')
            approval_preview = _attr_or_key(report, 'approval_preview', {}) or {}
            data_freshness = _attr_or_key(report, 'data_freshness', {}) or {}
            trend_preview = _attr_or_key(report, 'trend_preview', {}) or {}
            queue_name = str(_attr_or_key(report, 'queue_name', '') or '').strip()
            if not queue_name:
                continue
            rows.append(
                {
                    'queue_name': queue_name,
                    'status': str(_attr_or_key(report, 'status', 'unknown') or 'unknown').strip(),
                    'ok': bool(_attr_or_key(report, 'ok', False)),
                    'pending_jobs': int(_attr_or_key(report, 'pending_jobs', 0) or 0),
                    'active_claims': int(_attr_or_key(report, 'active_claims', 0) or 0),
                    'dead_letter_jobs': int(_attr_or_key(report, 'dead_letter_jobs', 0) or 0),
                    'reasons': tuple(str(item).strip() for item in tuple(_attr_or_key(report, 'reasons', ()) or ()) if str(item).strip()),
                    'janitor_stale_seconds': _attr_or_key(report, 'janitor_stale_seconds'),
                    'leader_stale_seconds': _attr_or_key(report, 'leader_stale_seconds'),
                    'backpressure_reason': _attr_or_key(_attr_or_key(backpressure, 'global_verdict'), 'reason') if backpressure is not None else None,
                    'backpressure_alert_count': len(_attr_or_key(backpressure, 'alerts', ()) or ()) if backpressure is not None else 0,
                    'starving_tenants': int(_attr_or_key(backpressure, 'starving_tenants', 0) or 0) if backpressure is not None else 0,
                    'approval_required_count': int(_attr_or_key(approval_preview, 'approval_required_count', 0) or 0),
                    'freshness_state': _attr_or_key(data_freshness, 'state'),
                    'pending_direction': _attr_or_key(trend_preview, 'pending_direction'),
                }
            )
        return self.build({'tenant_id': required_tenant_id, 'rows': tuple(rows)})


__all__ = ['CANON_WEB_QUEUE_HEALTH_CARD', 'QueueHealthCard']
