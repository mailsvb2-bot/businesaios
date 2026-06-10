from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

CANON_WEB_ROUTES = True

_ALLOWED_PAGES = {
    "AdminPage",
    "AnalyticsPage",
    "SecurityPage",
    "ApprovalsPage",
    "ConnectorAdminPage",
    "ProviderTokensAdminPage",
    "PlatformControlCenterPage",
    "QueueOpsPage",
    "QueueHistoryPage",
    "RuntimeAlertsPage",
    "ClientOutcomesPage",
}

_DEFAULT_ROUTES = (
    ("/web/admin", "AdminPage", True),
    ("/web/analytics", "AnalyticsPage", True),
    ("/web/security", "SecurityPage", True),
    ("/web/approvals", "ApprovalsPage", True),
    ("/web/connectors", "ConnectorAdminPage", True),
    ("/web/provider-tokens", "ProviderTokensAdminPage", True),
    ("/web/platform-admin", "PlatformControlCenterPage", True),
    ("/web/queue-ops", "QueueOpsPage", True),
    ("/web/queue-history", "QueueHistoryPage", True),
    ("/web/runtime-alerts", "RuntimeAlertsPage", True),
    ("/web/client-outcomes", "ClientOutcomesPage", True),
)


@dataclass(frozen=True)
class RouteDefinition:
    path: str
    page: str
    tenant_required: bool = True
    auth_required: bool = True

    def as_row(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        tenant_text = str(tenant_id or '').strip()
        status = 'ok'
        if self.tenant_required and not tenant_text:
            status = 'tenant_required'
        return {
            'path': str(self.path),
            'page': str(self.page),
            'tenant_required': bool(self.tenant_required),
            'auth_required': bool(self.auth_required),
            'status': status,
        }


@dataclass
class Routes:
    items: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_iterable(cls, items: Iterable[str]) -> "Routes":
        return cls(items=tuple(str(item) for item in items))

    def build_default(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        routes = tuple(RouteDefinition(path=path, page=page, tenant_required=tenant_required) for path, page, tenant_required in _DEFAULT_ROUTES)
        return self.build({'tenant_id': tenant_id, 'routes': routes})

    def build(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        tenant_id = str(payload.get('tenant_id') or '').strip() or None
        raw_routes = tuple(payload.get('routes') or ())
        definitions: list[RouteDefinition] = []
        for item in raw_routes:
            if isinstance(item, RouteDefinition):
                definition = item
            else:
                data = dict(item) if isinstance(item, Mapping) else {}
                definition = RouteDefinition(
                    path=str(data.get('path') or '').strip(),
                    page=str(data.get('page') or '').strip(),
                    tenant_required=bool(data.get('tenant_required', True)),
                    auth_required=bool(data.get('auth_required', True)),
                )
            if not definition.path or definition.page not in _ALLOWED_PAGES:
                continue
            definitions.append(definition)
        rows = tuple(defn.as_row(tenant_id=tenant_id) for defn in definitions)
        return {
            'kind': 'route_table',
            'payload': {
                'tenant_id': tenant_id,
                'routes': rows,
                'summary': {
                    'count': len(rows),
                    'auth_required_count': sum(1 for row in rows if row['auth_required']),
                    'tenant_required_count': sum(1 for row in rows if row['tenant_required']),
                },
            },
        }


__all__ = ["CANON_WEB_ROUTES", "RouteDefinition", "Routes"]
