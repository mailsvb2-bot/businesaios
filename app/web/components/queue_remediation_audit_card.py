from __future__ import annotations

"""Queue remediation audit card for operator views."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUEUE_REMEDIATION_AUDIT_CARD = True


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or '').strip()
    return text or None


def _has_redaction(value: Any) -> bool:
    if value == '[redacted]' or value == '[truncated]':
        return True
    if isinstance(value, Mapping):
        return any(str(key) == '__truncated__' or _has_redaction(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_has_redaction(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class QueueRemediationAuditCard:
    kind: str = 'queue_remediation_audit_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        queue_name = str(normalized.get('queue_name') or '').strip()
        rows = [dict(item or {}) for item in tuple(normalized.get('rows', ()) or ())]
        if not rows and normalized.get('timeline') is not None:
            rows = [dict(item or {}) for item in tuple(normalized.get('timeline', ()) or ())]
        rows.sort(
            key=lambda item: (
                str(item.get('recorded_at') or item.get('executed_at') or item.get('generated_at') or ''),
                str(item.get('action') or item.get('hook_code') or ''),
            ),
            reverse=True,
        )
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'queue_name': queue_name,
                'rows': tuple(rows),
                'row_count': len(rows),
                'executed_count': sum(1 for row in rows if bool(row.get('executed'))),
                'route_event_count': sum(1 for row in rows if str(row.get('entry_type') or '') == 'route_event'),
                'tenant_bound': True,
                'review_required_count': sum(1 for row in rows if str(row.get('entry_type') or '') == 'execution' and not bool(row.get('executed', False))),
                'redacted_row_count': sum(1 for row in rows if _has_redaction(row.get('metadata'))),
            },
        )

    def build_from_audit(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        plans: Iterable[Any] = (),
        executions: Iterable[Any] = (),
        route_history: Iterable[Any] = (),
        limit: int = 100,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        rows: list[dict[str, Any]] = []
        for item in plans:
            rows.append(
                {
                    'entry_type': 'plan',
                    'generated_at': _iso(getattr(item, 'generated_at', None)),
                    'hook_count': len(tuple(getattr(item, 'hooks', ()) or ())),
                    'hooks': tuple(getattr(item, 'hooks', ()) or ()),
                }
            )
        for item in executions:
            rows.append(
                {
                    'entry_type': 'execution',
                    'hook_code': str(getattr(item, 'hook_code', '') or '').strip(),
                    'executed': bool(getattr(item, 'executed', False)),
                    'reason': str(getattr(item, 'reason', '') or '').strip(),
                    'category': str(getattr(item, 'category', '') or '').strip(),
                    'metadata': dict(getattr(item, 'metadata', {}) or {}),
                    'executed_at': _iso(getattr(item, 'executed_at', None)),
                }
            )
        for item in route_history:
            rows.append(
                {
                    'entry_type': 'route_event',
                    'action': str(getattr(item, 'action', '') or '').strip(),
                    'source': str(getattr(item, 'source', '') or '').strip(),
                    'actor_id': getattr(item, 'actor_id', None),
                    'request_id': getattr(item, 'request_id', None),
                    'status': str(getattr(item, 'status', '') or '').strip(),
                    'metadata': dict(getattr(item, 'metadata', {}) or {}),
                    'recorded_at': _iso(getattr(item, 'recorded_at', None)),
                }
            )
        return self.build({'tenant_id': required_tenant_id, 'queue_name': queue_name, 'rows': tuple(rows[: max(1, int(limit))])})


__all__ = ['CANON_WEB_QUEUE_REMEDIATION_AUDIT_CARD', 'QueueRemediationAuditCard']
