from __future__ import annotations

from dataclasses import dataclass

from billing.money import legacy_float, money_decimal


@dataclass(frozen=True)
class BillableEvent:
    lead_fingerprint: str
    outcome_kind: str
    amount: float
    currency: str = "RUB"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "amount",
            legacy_float(money_decimal(self.amount), name="amount"),
        )
        currency = str(self.currency or "").strip().upper()
        if not currency:
            raise ValueError("currency is required")
        object.__setattr__(self, "currency", currency)
