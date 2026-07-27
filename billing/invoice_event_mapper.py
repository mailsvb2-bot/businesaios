from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping

from billing.billable_event import BillableEvent
from billing.money import (
    legacy_float,
    money_decimal,
    quantity_decimal,
    rate_decimal,
)
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

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "quantity",
            legacy_float(quantity_decimal(self.quantity), name="quantity"),
        )
        object.__setattr__(
            self,
            "unit_price",
            legacy_float(rate_decimal(self.unit_price), name="unit_price"),
        )
        object.__setattr__(
            self,
            "amount",
            legacy_float(
                money_decimal(self.amount, name="amount", allow_negative=True),
                name="amount",
            ),
        )
        currency = str(self.currency or "").strip().upper()
        if not currency:
            raise ValueError("currency is required")
        object.__setattr__(self, "currency", currency)


class InvoiceEventMapper:
    """Pure usage -> invoice-safe translation.

    No invoice workflow ownership. No settlement ownership.
    No decision logic. Billing arithmetic is decimal-only; legacy floats are
    materialized only at DTO boundaries.
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

        quantity = quantity_decimal(record.quantity, name="quantity")

        if rate is None:
            unit_price = rate_decimal(
                billing_scope.unit_price(record.meter_key),
                name="unit_price",
            )
            currency = billing_scope.currency
            unit_name = "unit"
            included_units = Decimal("0")
        else:
            unit_price = rate_decimal(rate.unit_price, name="unit_price")
            currency = rate.currency
            unit_name = rate.unit_name
            included_units = quantity_decimal(
                rate.included_units,
                name="included_units",
            )

        if billing_scope is not None:
            override_price = billing_scope.meter_prices.get(record.meter_key)
            if override_price is not None:
                unit_price = rate_decimal(
                    override_price,
                    name="override_unit_price",
                )
            currency = billing_scope.currency or currency

        billable_units = max(Decimal("0"), quantity - included_units)
        amount = money_decimal(
            billable_units * unit_price,
            name="line_amount",
        )
        return InvoiceLineItem(
            meter_key=record.meter_key,
            quantity=legacy_float(quantity, name="quantity"),
            unit_price=legacy_float(unit_price, name="unit_price"),
            amount=legacy_float(amount, name="line_amount"),
            currency=str(currency).strip().upper(),
            unit_name=unit_name,
            labels=dict(record.labels),
            metadata={
                "included_units": legacy_float(
                    included_units,
                    name="included_units",
                ),
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
        line = self.build_line_item(
            record=record,
            plan=plan,
            billing_scope=billing_scope,
        )
        if line is None or money_decimal(line.amount, name="line_amount") <= 0:
            return None
        lead_fingerprint = str(
            record.metadata.get("resource_id")
            or record.idempotency_key
            or record.meter_key
        )
        return BillableEvent(
            lead_fingerprint=lead_fingerprint,
            outcome_kind=record.meter_key,
            amount=legacy_float(
                money_decimal(line.amount, name="billable_amount"),
                name="billable_amount",
            ),
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
            line = self.build_line_item(
                record=record,
                plan=plan,
                billing_scope=billing_scope,
            )
            if line is not None:
                items.append(line)
        return tuple(items)

    def summarize_by_meter(
        self,
        *,
        items: Iterable[InvoiceLineItem],
    ) -> dict[str, dict[str, float | str]]:
        exact: dict[str, dict[str, Decimal | str]] = {}
        for item in items:
            bucket = exact.setdefault(
                item.meter_key,
                {
                    "quantity": Decimal("0"),
                    "amount": Decimal("0"),
                    "currency": item.currency,
                },
            )
            bucket["quantity"] = quantity_decimal(
                bucket["quantity"],
                name="summary_quantity",
            ) + quantity_decimal(item.quantity, name="item_quantity")
            bucket["amount"] = money_decimal(
                bucket["amount"],
                name="summary_amount",
                allow_negative=True,
            ) + money_decimal(
                item.amount,
                name="item_amount",
                allow_negative=True,
            )

        summary: dict[str, dict[str, float | str]] = {}
        for meter_key, bucket in exact.items():
            summary[meter_key] = {
                "quantity": legacy_float(
                    quantity_decimal(bucket["quantity"], name="summary_quantity"),
                    name="summary_quantity",
                ),
                "amount": legacy_float(
                    money_decimal(
                        bucket["amount"],
                        name="summary_amount",
                        allow_negative=True,
                    ),
                    name="summary_amount",
                ),
                "currency": str(bucket["currency"]),
            }
        return summary


__all__ = [
    "CANON_INVOICE_EVENT_MAPPER",
    "InvoiceEventMapper",
    "InvoiceLineItem",
]
