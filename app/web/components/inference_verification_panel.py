from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_INFERENCE_VERIFICATION_PANEL = True


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class InferenceVerificationPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'inference_verification_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        top_reasons = []
        for item in tuple(normalized.get('top_reasons', ()) or ()):
            if not isinstance(item, Mapping):
                continue
            top_reasons.append(
                {
                    'reason': str(item.get('reason') or 'unknown'),
                    'count': _safe_int(item.get('count')),
                }
            )
        result = {
            'tenant_id': tenant_id,
            'title': 'Inference Verification',
            'accepted_count': _safe_int(normalized.get('accepted_count')),
            'rejected_count': _safe_int(normalized.get('rejected_count')),
            'top_reasons': tuple(top_reasons),
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
