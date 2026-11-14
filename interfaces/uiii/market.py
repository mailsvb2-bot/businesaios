"""Evidence-backed exact price comparisons; never a pricing decision."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceObservation:
    product_variant: str
    region: str
    unit: str
    currency: str
    terms: str
    amount: Decimal
    observed_at: datetime
    evidence_ref: str
    provider: str
    stock: int | None = None

    def __post_init__(self):
        if not all((self.product_variant, self.region, self.unit, self.currency,
                    self.terms, self.evidence_ref, self.provider)):
            raise ValueError("comparison context and evidence required")
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite() or self.amount < 0:
            raise ValueError("finite exact nonnegative amount required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observation timezone required")
        if self.stock is not None and (type(self.stock) is not int or self.stock < 0):
            raise ValueError("unknown stock must be None, never a synthetic zero")

    def comparable_key(self):
        return (self.product_variant, self.region, self.unit, self.currency, self.terms)


def price_change(before: PriceObservation, after: PriceObservation, *, now: datetime, max_age_seconds: int):
    if now.tzinfo is None or max_age_seconds < 0:
        raise ValueError("invalid clock/freshness limit")
    if before.comparable_key() != after.comparable_key() or before.provider != after.provider:
        return {"status": "NOT_COMPARABLE", "delta": None}
    if after.observed_at <= before.observed_at or after.observed_at > now:
        return {"status": "INVALID_ORDER", "delta": None}
    if (now - after.observed_at).total_seconds() > max_age_seconds:
        return {"status": "STALE", "delta": None}
    return {
        "status": "OBSERVED_CHANGE",
        "delta": str(after.amount - before.amount),
        "relative_change": None if before.amount == 0 else str((after.amount - before.amount) / before.amount),
        "evidence_refs": [before.evidence_ref, after.evidence_ref],
        "causal_claim": False,
    }
