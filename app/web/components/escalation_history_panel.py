from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_ESCALATION_HISTORY_PANEL = True


@dataclass(frozen=True, slots=True)
class EscalationHistoryPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'escalation_history_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = []
        for item in tuple(normalized.get('events', ()) or ()):
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    'from_tier': str(item.get('from_tier') or 'unknown'),
                    'to_tier': str(item.get('to_tier') or 'unknown'),
                    'reason': str(item.get('reason') or 'unknown'),
                    'ts': float(item.get('ts') or 0.0),
                }
            )
        result = {
            'tenant_id': tenant_id,
            'title': 'Escalation History',
            'events': tuple(rows),
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
