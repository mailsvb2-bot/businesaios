from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_INFERENCE_TIER_PANEL = True


def _text(value: Any) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class InferenceTierPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'inference_tier_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        result = {
            'tenant_id': tenant_id,
            'title': 'Inference Tier',
            'active_tier': _text(normalized.get('active_tier')) or 'unknown',
            'reason': _text(normalized.get('reason')) or 'not_provided',
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
