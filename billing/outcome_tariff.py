from __future__ import annotations

from dataclasses import dataclass

from billing.money import legacy_float, money_decimal, rate_decimal


@dataclass(frozen=True)
class OutcomeTariff:
    qualified_lead_price: float = 0.0
    booking_price: float = 0.0
    conversion_fee_rate: float = 0.0

    def __post_init__(self) -> None:
        lead_price = money_decimal(
            self.qualified_lead_price,
            name="qualified_lead_price",
        )
        booking_price = money_decimal(self.booking_price, name="booking_price")
        conversion_rate = rate_decimal(
            self.conversion_fee_rate,
            name="conversion_fee_rate",
        )
        object.__setattr__(
            self,
            "qualified_lead_price",
            legacy_float(lead_price, name="qualified_lead_price"),
        )
        object.__setattr__(
            self,
            "booking_price",
            legacy_float(booking_price, name="booking_price"),
        )
        object.__setattr__(
            self,
            "conversion_fee_rate",
            legacy_float(conversion_rate, name="conversion_fee_rate"),
        )

    def price_for(self, outcome_kind: str, revenue_amount: float = 0.0) -> float:
        if outcome_kind == "qualified_lead":
            return self.qualified_lead_price
        if outcome_kind == "booking":
            return self.booking_price
        if outcome_kind == "conversion":
            revenue = money_decimal(revenue_amount, name="revenue_amount")
            rate = rate_decimal(
                self.conversion_fee_rate,
                name="conversion_fee_rate",
            )
            amount = money_decimal(revenue * rate, name="conversion_price")
            return legacy_float(amount, name="conversion_price")
        return 0.0
