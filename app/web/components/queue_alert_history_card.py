from __future__ import annotations

"""Queue alert history card for operator views."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUEUE_ALERT_HISTORY_CARD = True


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or '').strip()
    return text or None


@dataclass(frozen=True, slots=True)
class QueueAlertHistoryCard:
    kind: str = 'queue_alert_history_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = [dict(item or {}) for item in tuple(normalized.get('rows', ()) or ())]
        for row in rows:
            row['tenant_id'] = tenant_id
        rows.sort(key=lambda item: (str(item.get('created_at') or ''), str(item.get('severity') or '')), reverse=True)
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'rows': tuple(rows),
                'alert_count': len(rows),
                'critical_count': sum(1 for row in rows if str(row.get('severity') or '') == 'critical'),
                'error_count': sum(1 for row in rows if str(row.get('severity') or '') == 'error'),
                'tenant_bound': True,
            },
        )

    def build_from_alerts(self, *, tenant_id: str, queue_name: str | None = None, alerts: Iterable[Any], limit: int = 100) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        selected_queue_name = str(queue_name or '').strip() or None
        rows: list[dict[str, Any]] = []
        for item in alerts:
            row_tenant_id = normalize_tenant_id(getattr(item, 'tenant_id', None))
            if row_tenant_id and row_tenant_id != required_tenant_id:
                continue
            item_queue_name = str(getattr(item, 'queue_name', '') or '').strip()
            if selected_queue_name is not None and item_queue_name != selected_queue_name:
                continue
            rows.append(
                {
                    'queue_name': item_queue_name,
                    'code': str(getattr(item, 'code', '') or '').strip(),
                    'severity': str(getattr(item, 'severity', 'warning') or 'warning').strip(),
                    'message': str(getattr(item, 'message', '') or '').strip(),
                    'created_at': _iso(getattr(item, 'created_at', None)),
                }
            )
            if len(rows) >= max(1, int(limit)):
                break
        return self.build({'tenant_id': required_tenant_id, 'rows': tuple(rows)})


__all__ = ['CANON_WEB_QUEUE_ALERT_HISTORY_CARD', 'QueueAlertHistoryCard']
