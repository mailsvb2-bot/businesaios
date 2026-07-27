from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from billing.money import legacy_float, money_decimal, rate_decimal

CANON_CLIENT_OUTCOME_INVOICE_LINE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeInvoiceLine:
    invoice_line_id: str
    tenant_id: str
    business_id: str
    order_id: str
    package_id: str
    period_key: str
    quantity: int
    unit_price: float
    amount: float
    currency: str
    description: str
    generated_at: datetime

    def __post_init__(self) -> None:
        price = rate_decimal(
            self.unit_price,
            name="unit_price",
            allow_negative=True,
        )
        amount = money_decimal(
            self.amount,
            name="amount",
            allow_negative=True,
        )
        currency = str(self.currency or "").strip().upper()
        if not currency:
            raise ValueError("currency is required")
        if isinstance(self.quantity, bool):
            raise ValueError("quantity must be an integer")
        quantity = int(self.quantity)
        if quantity != self.quantity:
            raise ValueError("quantity must be an integer")
        object.__setattr__(self, "unit_price", legacy_float(price, name="unit_price"))
        object.__setattr__(self, "amount", legacy_float(amount, name="amount"))
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "currency", currency)
