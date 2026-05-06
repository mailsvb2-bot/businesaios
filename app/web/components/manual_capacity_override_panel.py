from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_MANUAL_CAPACITY_OVERRIDE_PANEL = True


@dataclass(frozen=True, slots=True)
class ManualCapacityOverridePanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'manual_capacity_override_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        result = {
            'tenant_id': tenant_id,
            'title': 'Manual Capacity Override',
            'frozen': bool(normalized.get('frozen', False)),
            'active_tier': str(normalized.get('active_tier') or 'unknown'),
            'operator_required': True,
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
