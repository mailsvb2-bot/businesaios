from __future__ import annotations

"""SLO status card for admin/runtime views."""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from observability.slo_contract import SLOComparator
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_SLO_STATUS_CARD = True


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, *, default: int = 0, minimum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def _evaluate(definition: Any, reading: Mapping[str, Any]) -> dict[str, Any]:
    comparator = getattr(definition, 'comparator', None)
    comparator_value = str(getattr(comparator, 'value', comparator) or '').strip()
    observed_value = _safe_float(reading.get('value', 0.0), default=0.0)
    target_value = _safe_float(getattr(definition, 'target_value', 0.0), default=0.0)
    sample_count = _safe_int(reading.get('sample_count', 0), default=0, minimum=0)
    min_sample_count = _safe_int(getattr(definition, 'min_sample_count', 1), default=1, minimum=1)
    if sample_count < min_sample_count:
        compliant = False
        reason = 'insufficient_sample_count'
    elif comparator_value == SLOComparator.LTE.value:
        compliant = observed_value <= target_value
        reason = 'ok' if compliant else 'above_target'
    else:
        compliant = observed_value >= target_value
        reason = 'ok' if compliant else 'below_target'
    return {
        'slo_id': str(getattr(definition, 'slo_id', '') or '').strip(),
        'tenant_id': str(getattr(definition, 'tenant_id', '') or '').strip(),
        'sli_name': str(getattr(definition, 'sli_name', '') or '').strip(),
        'sli_kind': str(getattr(getattr(definition, 'sli_kind', None), 'value', getattr(definition, 'sli_kind', '')) or '').strip(),
        'comparator': comparator_value,
        'observed_value': observed_value,
        'target_value': target_value,
        'sample_count': sample_count,
        'min_sample_count': min_sample_count,
        'is_compliant': compliant,
        'reason': reason,
        'labels': dict(reading.get('labels', {}) or {}),
    }


@dataclass(frozen=True, slots=True)
class SLOStatusCard:
    kind: str = 'slo_status_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = [dict(item or {}) for item in tuple(normalized.get('rows', ()) or ()) if str(dict(item or {}).get('tenant_id') or tenant_id).strip() in ('', tenant_id)]
        for row in rows:
            row['tenant_id'] = tenant_id
        rows.sort(key=lambda item: (str(item.get('is_compliant')), str(item.get('sli_name') or '')))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'rows': tuple(rows),
                'compliant_count': sum(1 for item in rows if bool(item.get('is_compliant'))),
                'non_compliant_count': sum(1 for item in rows if not bool(item.get('is_compliant'))),
                'tenant_bound': True,
            },
        )

    def build_from_definitions(
        self,
        *,
        tenant_id: str,
        definitions: Iterable[Any],
        readings: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        rows = []
        for definition in definitions:
            if str(getattr(definition, 'tenant_id', '') or '').strip() != required_tenant_id:
                continue
            reading = dict(readings.get(str(getattr(definition, 'sli_name', '') or '').strip(), {}) or {})
            rows.append(_evaluate(definition, reading))
        return self.build({'tenant_id': required_tenant_id, 'rows': tuple(rows)})


__all__ = ['SLOStatusCard', 'CANON_WEB_SLO_STATUS_CARD']
