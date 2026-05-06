from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_INFERENCE_PROVIDER_HEALTH_PANEL = True


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class InferenceProviderHealthPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'inference_provider_health_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = []
        for item in tuple(normalized.get('providers', ()) or ()):
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    'provider_name': _text(item.get('provider_name')) or 'unknown',
                    'healthy': _safe_bool(item.get('healthy')),
                    'availability_score': _safe_float(item.get('availability_score')),
                    'latency_score': _safe_float(item.get('latency_score')),
                    'error_rate': _safe_float(item.get('error_rate')),
                    'saturation_score': _safe_float(item.get('saturation_score')),
                }
            )
        result = {
            'tenant_id': tenant_id,
            'title': 'Inference Provider Health',
            'rows': tuple(rows),
            'summary': {
                'provider_count': len(rows),
                'healthy_count': sum(1 for row in rows if row['healthy']),
                'degraded_count': sum(1 for row in rows if not row['healthy']),
            },
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
