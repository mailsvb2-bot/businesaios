from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_PROVIDER_MIX_PANEL = True


def _text(value: Any) -> str:
    return str(value or '').strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class ProviderMixPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'provider_mix_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = []
        seen: set[str] = set()
        for item in tuple(normalized.get('providers', ()) or ()):
            if not isinstance(item, Mapping):
                continue
            provider_name = _text(item.get('provider_name'))
            if not provider_name or provider_name in seen:
                continue
            seen.add(provider_name)
            rows.append(
                {
                    'provider_name': provider_name,
                    'traffic_share': round(max(0.0, _safe_float(item.get('traffic_share'))), 6),
                    'tier': _text(item.get('tier')) or 'unknown',
                }
            )
        rows.sort(key=lambda row: (-row['traffic_share'], row['provider_name']))
        result = {
            'tenant_id': tenant_id,
            'title': 'Inference Provider Mix',
            'providers': tuple(rows),
            'read_only': True,
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))
