from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_CONNECTOR_ADMIN_PAGE = True


def _normalize_connector_rows(connectors: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    rows = []
    for connector_id, payload in sorted(dict(connectors or {}).items()):
        item = dict(payload or {})
        status = str(item.get('status', 'unknown') or 'unknown').strip()
        rows.append(
            {
                'connector_id': str(connector_id),
                'status': status,
                'read': bool(item.get('read')),
                'write': bool(item.get('write')),
                'verify': bool(item.get('verify')),
                'supports_dry_run': bool(item.get('supports_dry_run')),
                'supports_idempotency': bool(item.get('supports_idempotency')),
                'production_ready': bool(item.get('production_ready')),
                'action_types': tuple(sorted(str(x).strip() for x in tuple(item.get('action_types', ()) or ()) if str(x).strip())),
                'maturity': str(item.get('maturity', '') or '').strip() or None,
            }
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class ConnectorAdminPage:
    kind: str = 'connector_admin_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows = tuple(dict(item or {}) for item in tuple(normalized.get('rows', ()) or ()))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Connector Admin',
                'rows': rows,
                'implemented_count': sum(1 for item in rows if str(item.get('status') or '') == 'implemented'),
                'production_ready_count': sum(1 for item in rows if bool(item.get('production_ready'))),
                'write_capable_count': sum(1 for item in rows if bool(item.get('write'))),
                'verify_capable_count': sum(1 for item in rows if bool(item.get('verify'))),
                'quick_actions': (
                    {'label': 'Ввести токен / ключ', 'path': '/web/provider-tokens'},
                    {'label': 'Проверить secret scope', 'path': '/control-plane/connectors/{connector_id}/secret-scope/dry-run'},
                ),
                'tenant_bound': True,
            },
        )

    def build_from_registry(self, *, tenant_id: str, connectors: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        return self.build({'tenant_id': require_tenant_id(tenant_id), 'rows': _normalize_connector_rows(connectors)})


__all__ = ['ConnectorAdminPage', 'CANON_WEB_CONNECTOR_ADMIN_PAGE']
