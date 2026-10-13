"""Paid program read-model over canonical Order, Billing and PSP checkout facts.

No entitlement table, second payment owner, or implicit delivery. A grant is
derived afresh at every enrollment/send/provider acceptance. Reversal evidence
must be supplied by a server-trusted authority; unknown means no access.
"""
from __future__ import annotations

from typing import Any

from application.commerce.phase18_commercial_order import _KIND, _required

CANON_PHASE18_PAID_PROGRAM_ACCESS_PROJECTION = True


class CanonicalPaidProgramAccess:
    """CommercialProgramPurchaseService remains the single decision owner."""

    def __init__(
        self, *, purchases: Any, checkouts: Any, reversal_reader: Any,
    ) -> None:
        if not callable(reversal_reader):
            raise TypeError("commercial_reversal_authority_required")
        if not callable(getattr(checkouts, "_saved", None)):
            raise TypeError("commercial_durable_checkout_owner_required")
        if not callable(getattr(purchases.invoices, "has_verified_commercial_settlement", None)):
            raise TypeError("commercial_invoice_evidence_owner_required")
        self._purchases = purchases
        self._checkouts = checkouts
        self._reversal_reader = reversal_reader

    def _verified_payment(
        self, *, tenant_id: str, business_id: str, order_id: str,
        invoice_id: str, amount_minor: int, currency: str,
    ) -> bool:
        checkout = self._checkouts._saved(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        if checkout is None:
            return False
        if (
            checkout.tenant_id != tenant_id or checkout.business_id != business_id
            or checkout.order_id != order_id or checkout.invoice_id != invoice_id
            or checkout.amount_minor != amount_minor or checkout.currency != currency
            or not checkout.provider_name or not checkout.external_reference
            or checkout.status != "awaiting_payment"
        ):
            raise RuntimeError("commercial_access_checkout_provenance_invalid")
        return self._purchases.invoices.has_verified_commercial_settlement(
            tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id,
            provider_name=checkout.provider_name,
            external_reference=checkout.external_reference,
        )

    def require_access(
        self, *, tenant_id: str, business_id: str,
        program_id: str, customer_id: str,
    ) -> bool:
        """Conservative, fresh scoped projection; never persists a separate grant.

        The app owner can call this on every paid enrollment or lesson
        execution. Return exactly True only for an existing active order,
        full immutable PSP settlement and a non-reversed payment verified by
        the existing server-owned reversal authority.
        """
        tenant_id = _required("tenant_id", tenant_id)
        business_id = _required("business_id", business_id)
        program_id = _required("program_id", program_id)
        customer_id = _required("customer_id", customer_id)
        for order in self._purchases.orders.list_for_business(
            tenant_id=tenant_id, business_id=business_id,
        ):
            if order.order_kind != _KIND:
                continue
            current, link = self._purchases._read(
                tenant_id=tenant_id, business_id=business_id,
                order_id=order.order_id,
            )
            if link["program_id"] != program_id or link["customer_id"] != customer_id:
                continue
            ready = self._purchases.execution_readiness(
                tenant_id=tenant_id, business_id=business_id,
                order_id=current.order_id,
                payment_evidence_reader=self._verified_payment,
                reversal_reader=self._reversal_reader,
            )
            if ready.eligible:
                return True
        return False


__all__ = [
    "CANON_PHASE18_PAID_PROGRAM_ACCESS_PROJECTION", "CanonicalPaidProgramAccess",
]
