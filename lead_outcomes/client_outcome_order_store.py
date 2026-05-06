from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from registry.base_registry import BaseRegistry
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientOutcomePackage


CANON_CLIENT_OUTCOME_ORDER_STORE = True


class ClientOutcomeOrderStore(BaseRegistry):
    """
    Auditable owner-surface for persisted client outcome orders.
    Stores exactly the commercial contract that was selected.
    """

    def __init__(self) -> None:
        super().__init__(kind='client_outcome_order')

    def save(self, order: ClientOutcomeOrder) -> None:
        self.register(
            order.order_id,
            {
                'order_id': order.order_id,
                'tenant_id': order.tenant_id,
                'business_id': order.business_id,
                'package': {
                    'package_id': order.package.package_id,
                    'label': order.package.label,
                    'requested_clients': order.package.requested_clients,
                    'price_per_verified_client': order.package.price_per_verified_client,
                    'currency': order.package.currency,
                    'attribution_window_days': order.package.attribution_window_days,
                    'new_client_window_days': order.package.new_client_window_days,
                    'allow_returning_clients': order.package.allow_returning_clients,
                    'require_payment_proof': order.package.require_payment_proof,
                    'require_crm_proof': order.package.require_crm_proof,
                    'trust_tier': order.package.trust_tier,
                },
                'created_at': order.created_at.isoformat(),
                'metadata': dict(order.metadata),
            },
        )

    def get_order(self, order_id: str) -> ClientOutcomeOrder | None:
        try:
            payload = dict(super().get(str(order_id)))
        except KeyError:
            return None
        return self._order_from_payload(payload)

    def amend_order(
        self,
        *,
        now: datetime,
        order_id: str,
        package: ClientOutcomePackage,
        metadata: dict[str, Any] | None = None,
    ) -> ClientOutcomeOrder | None:
        current = self.get_order(order_id)
        if current is None:
            return None
        normalized_package = package.normalized_copy()
        amendment_meta = dict(metadata or {})
        amendments = list(current.metadata.get('amendments') or [])
        next_count = int(current.metadata.get('amendment_count') or 0) + 1
        amendments.append({
            'amendment_index': next_count,
            'amended_at': now.isoformat(),
            'from_package_id': current.package.package_id,
            'to_package_id': normalized_package.package_id,
            'from_requested_clients': current.package.requested_clients,
            'to_requested_clients': normalized_package.requested_clients,
            'from_price_per_verified_client': current.package.price_per_verified_client,
            'to_price_per_verified_client': normalized_package.price_per_verified_client,
            'currency': normalized_package.currency,
            'metadata': amendment_meta,
        })
        next_metadata = dict(current.metadata)
        amendment_fingerprints = list(current.metadata.get('amendment_fingerprints') or ())
        amendment_fingerprint_value = amendment_meta.get('amendment_fingerprint')
        if amendment_fingerprint_value not in (None, '') and str(amendment_fingerprint_value) not in amendment_fingerprints:
            amendment_fingerprints.append(str(amendment_fingerprint_value))
        next_metadata['amendment_count'] = next_count
        next_metadata['amendments'] = amendments
        next_metadata['amendment_fingerprints'] = amendment_fingerprints
        if amendment_meta:
            next_metadata['last_amendment'] = amendment_meta
        amended = replace(current, package=normalized_package, metadata=next_metadata)
        self.save(amended)
        return amended

    def _order_from_payload(self, payload: dict[str, Any]) -> ClientOutcomeOrder:
        package_payload = dict(payload['package'])
        return ClientOutcomeOrder(
            order_id=str(payload['order_id']),
            tenant_id=str(payload['tenant_id']),
            business_id=str(payload['business_id']),
            package=ClientOutcomePackage(
                package_id=str(package_payload['package_id']),
                label=str(package_payload['label']),
                requested_clients=int(package_payload['requested_clients']),
                price_per_verified_client=float(package_payload['price_per_verified_client']),
                currency=str(package_payload['currency']),
                attribution_window_days=int(package_payload['attribution_window_days']),
                new_client_window_days=int(package_payload['new_client_window_days']),
                allow_returning_clients=bool(package_payload['allow_returning_clients']),
                require_payment_proof=bool(package_payload['require_payment_proof']),
                require_crm_proof=bool(package_payload['require_crm_proof']),
                trust_tier=str(package_payload['trust_tier']),
            ).normalized_copy(),
            created_at=datetime.fromisoformat(str(payload['created_at'])),
            metadata=dict(payload.get('metadata') or {}),
        )


@dataclass(frozen=True, slots=True)
class ClientOutcomeOrderPersistenceService:
    store: ClientOutcomeOrderStore

    def persist(self, order: ClientOutcomeOrder) -> ClientOutcomeOrder:
        self.store.save(order)
        return order

    def get_order(self, order_id: str) -> ClientOutcomeOrder | None:
        return self.store.get_order(order_id)

    def amend_order(self, *, now: datetime, order_id: str, package: ClientOutcomePackage, metadata: dict[str, Any] | None = None) -> ClientOutcomeOrder | None:
        return self.store.amend_order(now=now, order_id=order_id, package=package, metadata=metadata)
