from __future__ import annotations

"""Queue rollup timeline card for operator views."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_QUEUE_ROLLUP_TIMELINE_CARD = True


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or '').strip()
    return text or None


@dataclass(frozen=True, slots=True)
class QueueRollupTimelineCard:
    kind: str = 'queue_rollup_timeline_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = [dict(item or {}) for item in tuple(normalized.get('rows', ()) or ())]
        for row in rows:
            row['tenant_id'] = tenant_id
        rows.sort(key=lambda item: (str(item.get('window_start') or ''), str(item.get('queue_name') or '')), reverse=True)
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'rows': tuple(rows),
                'window_count': len(rows),
                'critical_windows': sum(1 for row in rows if str(row.get('latest_status') or '') == 'critical'),
                'degraded_windows': sum(1 for row in rows if str(row.get('latest_status') or '') == 'degraded'),
                'tenant_bound': True,
            },
        )

    def build_from_window_summaries(self, *, tenant_id: str, queue_name: str, windows: Iterable[Any]) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        rows: list[dict[str, Any]] = []
        for window in windows:
            if str(getattr(window, 'tenant_id', '') or '').strip() != required_tenant_id:
                continue
            if str(getattr(window, 'queue_name', '') or '').strip() != str(queue_name).strip():
                continue
            rows.append(
                {
                    'queue_name': str(getattr(window, 'queue_name', '') or '').strip(),
                    'window_start': _iso(getattr(window, 'window_start', None)),
                    'window_end': _iso(getattr(window, 'window_end', None)),
                    'samples': int(getattr(window, 'samples', 0) or 0),
                    'latest_status': str(getattr(window, 'latest_status', 'unknown') or 'unknown').strip(),
                    'latest_ok': bool(getattr(window, 'latest_ok', False)),
                    'max_pending_jobs': int(getattr(window, 'max_pending_jobs', 0) or 0),
                    'max_active_claims': int(getattr(window, 'max_active_claims', 0) or 0),
                    'max_dead_letter_jobs': int(getattr(window, 'max_dead_letter_jobs', 0) or 0),
                    'total_alert_count': int(getattr(window, 'total_alert_count', 0) or 0),
                    'total_critical_alert_count': int(getattr(window, 'total_critical_alert_count', 0) or 0),
                }
            )
        return self.build({'tenant_id': required_tenant_id, 'rows': tuple(rows)})


__all__ = ['CANON_WEB_QUEUE_ROLLUP_TIMELINE_CARD', 'QueueRollupTimelineCard']
