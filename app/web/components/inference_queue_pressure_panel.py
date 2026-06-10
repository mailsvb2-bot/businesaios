from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_INFERENCE_QUEUE_PRESSURE_PANEL = True


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class InferenceQueuePressurePanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'inference_queue_pressure_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        queue_depth = _safe_int(normalized.get('queue_depth'))
        backlog_age_seconds = _safe_int(normalized.get('backlog_age_seconds'))
        result = {
            'tenant_id': tenant_id,
            'title': 'Inference Queue Pressure',
            'queue_depth': queue_depth,
            'backlog_age_seconds': backlog_age_seconds,
            'operator_attention_required': queue_depth > 100 or backlog_age_seconds > 180,
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
