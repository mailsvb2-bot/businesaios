from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from billing.billable_event import BillableEvent


class InvoiceBuilder:
    def build(self, events: Iterable[BillableEvent], *, invoice_id: str) -> dict:
        items = list(events)
        totals = defaultdict(float)
        for item in items:
            totals[item.currency] += float(item.amount)
        return {
            'invoice_id': invoice_id,
            'line_count': len(items),
            'totals': {currency: round(amount, 2) for currency, amount in totals.items()},
            'items': [item.__dict__.copy() for item in items],
        }
