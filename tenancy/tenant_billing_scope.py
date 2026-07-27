from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from billing.money import legacy_float, money_decimal, quantity_decimal, rate_decimal
from core.tenancy.normalization import require_tenant_id


CANON_TENANT_BILLING_SCOPE = True


class BillingMode(str, Enum):
    INTERNAL = "internal"
    PREPAID = "prepaid"
    POSTPAID = "postpaid"
    INVOICE = "invoice"


@dataclass(frozen=True)
class TenantBillingScope:
    tenant_id: str
    mode: BillingMode = BillingMode.POSTPAID
    currency: str = "USD"
    customer_id: str | None = None
    invoice_enabled: bool = True
    allow_overage: bool = False
    meter_prices: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.currency or "").strip():
            raise ValueError("currency is required")
        for meter_name, price in self.meter_prices.items():
            if not str(meter_name or "").strip():
                raise ValueError("meter name is required")
            rate_decimal(price, name=f"meter_prices[{meter_name}]")

    def unit_price(self, meter_name: str, *, default: float = 0.0) -> float:
        self.validate()
        name = str(meter_name or "").strip()
        if not name:
            raise ValueError("meter_name is required")
        value = rate_decimal(
            self.meter_prices.get(name, default),
            name=f"meter_prices[{name}]",
        )
        return legacy_float(value, name="unit_price")

    def estimate_charge(self, *, meter_name: str, quantity: float) -> float:
        normalized_quantity = quantity_decimal(quantity, name="quantity")
        unit_price = rate_decimal(self.unit_price(meter_name), name="unit_price")
        charge = money_decimal(normalized_quantity * unit_price, name="charge")
        return legacy_float(charge, name="charge")


__all__ = ["BillingMode", "CANON_TENANT_BILLING_SCOPE", "TenantBillingScope"]
