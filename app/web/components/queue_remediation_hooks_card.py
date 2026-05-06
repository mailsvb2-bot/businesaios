from __future__ import annotations

"""Queue remediation hooks card for operator/admin views."""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_QUEUE_REMEDIATION_HOOKS_CARD = True


@dataclass(frozen=True, slots=True)
class QueueRemediationHooksCard:
    kind: str = 'queue_remediation_hooks_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        queue_name = str(normalized.get('queue_name') or '').strip()
        hooks = [dict(item or {}) for item in tuple(normalized.get('hooks', ()) or ())]
        for row in hooks:
            row['tenant_id'] = tenant_id
            row['queue_name'] = queue_name or str(row.get('queue_name') or '').strip()
        hooks.sort(key=lambda item: (str(item.get('severity') or ''), str(item.get('code') or '')), reverse=True)
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'queue_name': queue_name,
                'hooks': tuple(hooks),
                'hook_count': len(hooks),
                'critical_count': sum(1 for row in hooks if str(row.get('severity') or '') == 'critical'),
                'operator_required_count': sum(1 for row in hooks if bool(row.get('operator_required', True))),
                'tenant_bound': True,
            },
        )

    def build_from_hooks(self, *, tenant_id: str, queue_name: str, hooks: Iterable[Any]) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        rows: list[dict[str, Any]] = []
        for hook in hooks:
            if str(getattr(hook, 'tenant_id', '') or '').strip() != required_tenant_id:
                continue
            if str(getattr(hook, 'queue_name', '') or '').strip() != str(queue_name).strip():
                continue
            rows.append(
                {
                    'code': str(getattr(hook, 'code', '') or '').strip(),
                    'label': str(getattr(hook, 'label', '') or '').strip(),
                    'description': str(getattr(hook, 'description', '') or '').strip(),
                    'severity': str(getattr(hook, 'severity', 'warning') or 'warning').strip(),
                    'operator_required': bool(getattr(hook, 'operator_required', True)),
                }
            )
        return self.build({'tenant_id': required_tenant_id, 'queue_name': queue_name, 'hooks': tuple(rows)})


__all__ = ['CANON_WEB_QUEUE_REMEDIATION_HOOKS_CARD', 'QueueRemediationHooksCard']
