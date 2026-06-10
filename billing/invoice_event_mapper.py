from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from billing.billable_event import BillableEvent
from billing.plan_contract import BillingPlanSpec
from billing.usage_meter import UsageRecord
from tenancy.tenant_billing_scope import TenantBillingScope

CANON_INVOICE_EVENT_MAPPER = True


@dataclass(frozen=True)
class InvoiceLineItem:
    meter_key: str
    quantity: float
    unit_price: float
    amount: float
    currency: str
    unit_name: str = "unit"
    labels: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)


class InvoiceEventMapper:
    """Pure usage -> invoice-safe translation.

    No invoice workflow ownership. No settlement ownership.
    No decision logic.
    """

    def build_line_item(
        self,
        *,
        record: UsageRecord,
        plan: BillingPlanSpec,
        billing_scope: TenantBillingScope | None = None,
    ) -> InvoiceLineItem | None:
        rate = plan.rate_for(record.meter_key)
        if rate is None and billing_scope is None:
            return None

        quantity = float(record.quantity)
        if quantity < 0:
            raise ValueError("quantity must be >= 0")

        if rate is None:
            unit_price = billing_scope.unit_price(record.meter_key)
            currency = billing_scope.currency
            unit_name = "unit"
            included_units = 0.0
        else:
            unit_price = float(rate.unit_price)
            currency = rate.currency
            unit_name = rate.unit_name
            included_units = float(rate.included_units)

        if billing_scope is not None:
            override_price = billing_scope.meter_prices.get(record.meter_key)
            if override_price is not None:
                unit_price = float(override_price)
            currency = billing_scope.currency or currency

        amount = round(max(0.0, quantity - included_units) * float(unit_price), 6)
        return InvoiceLineItem(
            meter_key=record.meter_key,
            quantity=quantity,
            unit_price=float(unit_price),
            amount=float(amount),
            currency=str(currency).strip().upper(),
            unit_name=unit_name,
            labels=dict(record.labels),
            metadata={
                "included_units": included_units,
                **dict(record.metadata),
            },
        )

    def build_billable_event(
        self,
        *,
        record: UsageRecord,
        plan: BillingPlanSpec,
        billing_scope: TenantBillingScope | None = None,
    ) -> BillableEvent | None:
        line = self.build_line_item(record=record, plan=plan, billing_scope=billing_scope)
        if line is None or line.amount <= 0:
            return None
        lead_fingerprint = str(record.metadata.get("resource_id") or record.idempotency_key or record.meter_key)
        return BillableEvent(
            lead_fingerprint=lead_fingerprint,
            outcome_kind=record.meter_key,
            amount=float(line.amount),
            currency=line.currency,
        )

    def map_usage(
        self,
        *,
        records: Iterable[UsageRecord],
        plan: BillingPlanSpec,
        billing_scope: TenantBillingScope | None = None,
    ) -> tuple[InvoiceLineItem, ...]:
        items: list[InvoiceLineItem] = []
        for record in records:
            line = self.build_line_item(record=record, plan=plan, billing_scope=billing_scope)
            if line is not None:
                items.append(line)
        return tuple(items)

    def summarize_by_meter(self, *, items: Iterable[InvoiceLineItem]) -> dict[str, dict[str, float | str]]:
        summary: dict[str, dict[str, float | str]] = {}
        for item in items:
            bucket = summary.setdefault(
                item.meter_key,
                {"quantity": 0.0, "amount": 0.0, "currency": item.currency},
            )
            bucket["quantity"] = round(float(bucket["quantity"]) + float(item.quantity), 6)
            bucket["amount"] = round(float(bucket["amount"]) + float(item.amount), 6)
        return summary


__all__ = [
    "CANON_INVOICE_EVENT_MAPPER",
    "InvoiceEventMapper",
    "InvoiceLineItem",
]
