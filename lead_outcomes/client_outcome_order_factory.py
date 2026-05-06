from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Any
from uuid import uuid4

from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientOutcomePackage
from lead_outcomes.client_outcome_package_catalog import ClientOutcomePackageCatalog

CANON_CLIENT_OUTCOME_ORDER_FACTORY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class ClientOutcomeOrderFactory:
    package_catalog: ClientOutcomePackageCatalog

    def create_for_package_id(self, *, now: datetime, tenant_id: str, business_id: str, package_id: str, metadata: Mapping[str, object] | None = None) -> ClientOutcomeOrder:
        package = self.package_catalog.get_by_id(package_id)
        return self._build_order(now=now, tenant_id=tenant_id, business_id=business_id, package=package, metadata=metadata)

    def create_for_requested_clients(self, *, now: datetime, tenant_id: str, business_id: str, requested_clients: int, metadata: Mapping[str, object] | None = None) -> ClientOutcomeOrder:
        package = self.package_catalog.get_by_requested_clients(requested_clients)
        return self._build_order(now=now, tenant_id=tenant_id, business_id=business_id, package=package, metadata=metadata)

    def _build_order(self, *, now: datetime, tenant_id: str, business_id: str, package: ClientOutcomePackage, metadata: Mapping[str, object] | None = None) -> ClientOutcomeOrder:
        return ClientOutcomeOrder(
            order_id=f'client-outcome-order:{uuid4().hex}',
            tenant_id=str(tenant_id or '').strip(),
            business_id=str(business_id or '').strip(),
            package=package.normalized_copy(),
            created_at=now,
            metadata=_safe_dict(metadata),
        )
