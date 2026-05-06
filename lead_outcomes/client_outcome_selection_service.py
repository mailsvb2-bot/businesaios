from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Any

from lead_outcomes.client_outcome_amendment_idempotency import amendment_fingerprint
from lead_outcomes.client_outcome_amendment_policy import can_amend_for_commercial_status
from lead_outcomes.client_outcome_commercial_state_store import ClientOutcomeCommercialStateService
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder
from lead_outcomes.client_outcome_order_factory import ClientOutcomeOrderFactory
from lead_outcomes.client_outcome_order_store import ClientOutcomeOrderPersistenceService
from lead_outcomes.client_outcome_package_catalog import ClientOutcomePackageCatalog

CANON_CLIENT_OUTCOME_SELECTION_SERVICE = True


def _text(value: object) -> str:
    return str(value or '').strip()


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class ClientOutcomeSelectionInput:
    tenant_id: str
    business_id: str
    package_id: str = ''
    requested_clients: int = 0
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ClientOutcomeSelectionResult:
    order: ClientOutcomeOrder
    selection_mode: str
    requested_clients: int
    package_id: str


@dataclass(frozen=True, slots=True)
class ClientOutcomeSelectionService:
    package_catalog: ClientOutcomePackageCatalog
    order_factory: ClientOutcomeOrderFactory
    persistence_service: ClientOutcomeOrderPersistenceService
    commercial_state_service: ClientOutcomeCommercialStateService | None = None

    def create_order(self, *, now: datetime, request: ClientOutcomeSelectionInput) -> ClientOutcomeSelectionResult:
        package_id = _text(request.package_id)
        if package_id:
            order = self.persistence_service.persist(self.order_factory.create_for_package_id(now=now, tenant_id=request.tenant_id, business_id=request.business_id, package_id=package_id, metadata=_safe_dict(request.metadata)))
            return ClientOutcomeSelectionResult(order=order, selection_mode='package_id', requested_clients=order.package.requested_clients, package_id=order.package.package_id)
        order = self.persistence_service.persist(self.order_factory.create_for_requested_clients(now=now, tenant_id=request.tenant_id, business_id=request.business_id, requested_clients=max(1, int(request.requested_clients)), metadata=_safe_dict(request.metadata)))
        return ClientOutcomeSelectionResult(order=order, selection_mode='requested_clients', requested_clients=order.package.requested_clients, package_id=order.package.package_id)

    def get_order(self, order_id: str) -> ClientOutcomeOrder | None:
        return self.persistence_service.get_order(order_id)


    def amend(self, *, now: datetime, order_id: str, request: ClientOutcomeSelectionInput) -> ClientOutcomeSelectionResult | None:
        current = self.persistence_service.get_order(order_id)
        if current is None:
            return None
        package_id = _text(request.package_id)
        if package_id:
            package = self.package_catalog.get_by_id(package_id)
            selection_mode = 'package_id'
        else:
            package = self.package_catalog.get_by_requested_clients(max(1, int(request.requested_clients)))
            selection_mode = 'requested_clients'

        if self.commercial_state_service is not None:
            commercial_state = self.commercial_state_service.get_latest_order_state(order_id=order_id)
            if commercial_state is not None and not can_amend_for_commercial_status(commercial_state.get('commercial_status')):
                raise ValueError('amendment_not_allowed_for_current_commercial_state')

        fingerprint = amendment_fingerprint(order_id=order_id, package_id=package.package_id, requested_clients=package.requested_clients)
        existing_fingerprints = tuple(str(item) for item in (current.metadata.get('amendment_fingerprints') or ()))
        if fingerprint in existing_fingerprints:
            return ClientOutcomeSelectionResult(order=current, selection_mode=selection_mode, requested_clients=current.package.requested_clients, package_id=current.package.package_id)

        metadata = _safe_dict(request.metadata)
        metadata['amendment_fingerprint'] = fingerprint
        amended = self.persistence_service.amend_order(now=now, order_id=order_id, package=package, metadata=metadata)
        if amended is None:
            return None
        return ClientOutcomeSelectionResult(order=amended, selection_mode=selection_mode, requested_clients=amended.package.requested_clients, package_id=amended.package.package_id)


ClientOutcomeSelectionService.select = ClientOutcomeSelectionService.create_order
