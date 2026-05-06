from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from security.connector_secret_scope import ConnectorSecretScope, SecretScopeBinding
from security.secret_contract import SecretRef


CANON_API_CONNECTOR_ADMIN_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_CONNECTOR_ADMIN_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class ConnectorAdminRouteHandlers:
    connector_secret_scope: ConnectorSecretScope = field(default_factory=ConnectorSecretScope)

    def register_scope(self, binding: SecretScopeBinding) -> dict[str, Any]:
        self.connector_secret_scope.register(binding)
        return {
            'tenant_id': binding.tenant_id,
            'connector_id': binding.connector_id,
            'allowed_secret_names': list(binding.allowed_secret_names),
            'allowed_secret_prefixes': list(binding.allowed_secret_prefixes),
            'allowed_secret_kinds': list(binding.allowed_secret_kinds),
            'allowed_operations': [item.value for item in binding.allowed_operations],
        }

    def dry_run_secret_access(
        self,
        *,
        tenant_id: str,
        connector_id: str,
        secret_name: str,
        mode: str = 'read',
        secret_kind: str | None = None,
    ) -> dict[str, Any]:
        ref = SecretRef(tenant_id=tenant_id, secret_name=secret_name)
        allowed = self.connector_secret_scope.is_allowed(
            ref=ref,
            connector_id=connector_id,
            mode=mode,
            secret_kind=secret_kind,
        )
        return {
            'tenant_id': tenant_id,
            'connector_id': connector_id,
            'secret_name': secret_name,
            'mode': mode,
            'secret_kind': secret_kind,
            'allowed': allowed,
        }

    def list_scope(self, *, tenant_id: str, connector_id: str) -> dict[str, Any]:
        return {
            'tenant_id': tenant_id,
            'connector_id': connector_id,
            'allowed': list(self.connector_secret_scope.allowed_for(tenant_id=tenant_id, connector_id=connector_id)),
        }


__all__ = [
    'CANON_API_CONNECTOR_ADMIN_ROUTE_HANDLERS',
    'ConnectorAdminRouteHandlers',
]
