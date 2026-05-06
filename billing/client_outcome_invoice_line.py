from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
