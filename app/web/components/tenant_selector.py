from __future__ import annotations

"""Tenant selector for admin/operator pages."""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_TENANT_SELECTOR = True


def _enum_value(value: Any) -> str:
    return str(getattr(value, 'value', value) or '').strip()


def _tenant_option(record: Any) -> dict[str, object]:
    return {
        'tenant_id': str(getattr(record, 'tenant_id', '') or '').strip(),
        'display_name': str(getattr(record, 'display_name', '') or getattr(record, 'tenant_id', '')).strip(),
        'status': _enum_value(getattr(record, 'status', '')),
        'plan': _enum_value(getattr(record, 'plan', '')),
        'data_region': str(getattr(record, 'data_region', '') or '').strip() or None,
        'aliases': tuple(sorted(str(item).strip() for item in tuple(getattr(record, 'aliases', ()) or ()) if str(item).strip())),
    }


@dataclass(frozen=True, slots=True)
class TenantSelector:
    kind: str = 'tenant_selector'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        selected_tenant_id = require_tenant_id(normalized.get('selected_tenant_id'))
        options = tuple(dict(item or {}) for item in tuple(normalized.get('options', ()) or ()))
        return build_kinded_payload(
            self.kind,
            {
                'selected_tenant_id': selected_tenant_id,
                'options': options,
                'count': len(options),
                'active_count': sum(1 for item in options if str(item.get('status') or '') == 'active'),
                'tenant_bound': True,
            },
        )

    def build_from_registry(
        self,
        *,
        selected_tenant_id: str,
        tenant_records: Iterable[Any],
    ) -> dict[str, Any]:
        required_selected_tenant_id = require_tenant_id(selected_tenant_id)
        options = []
        seen: set[str] = set()
        for item in tenant_records:
            row = _tenant_option(item)
            tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if not tenant_id or tenant_id in seen:
                continue
            row['tenant_id'] = tenant_id
            seen.add(tenant_id)
            options.append(row)
        options.sort(key=lambda item: (str(item.get('display_name') or ''), str(item.get('tenant_id') or '')))
        return self.build({'selected_tenant_id': required_selected_tenant_id, 'options': tuple(options)})


__all__ = ['TenantSelector', 'CANON_WEB_TENANT_SELECTOR']
