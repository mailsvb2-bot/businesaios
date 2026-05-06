from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_CONNECTOR_SCOPE = True


@dataclass(frozen=True)
class TenantConnectorScope:
    tenant_id: str
    allowed_connectors: tuple[str, ...] = ()
    denied_connectors: tuple[str, ...] = ()
    secret_scopes_by_connector: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    require_explicit_allowlist: bool = True

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if set(self.allowed_connectors) & set(self.denied_connectors):
            raise ValueError("same connector cannot be both allowed and denied")

    def allows(self, connector_id: str) -> bool:
        self.validate()
        connector = str(connector_id or "").strip()
        if not connector:
            return False
        if connector in set(self.denied_connectors):
            return False
        if not self.require_explicit_allowlist:
            return True
        return connector in set(self.allowed_connectors)

    def assert_allowed(self, connector_id: str) -> None:
        if not self.allows(connector_id):
            raise PermissionError(
                f"connector forbidden for tenant={self.tenant_id}: {connector_id}"
            )

    def allowed_secret_scopes(self, connector_id: str) -> tuple[str, ...]:
        self.assert_allowed(connector_id)
        return tuple(
            str(item)
            for item in self.secret_scopes_by_connector.get(str(connector_id), ())
        )


__all__ = ["CANON_TENANT_CONNECTOR_SCOPE", "TenantConnectorScope"]
