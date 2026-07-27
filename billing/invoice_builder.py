from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from billing.billable_event import BillableEvent
from billing.money import legacy_float, money_decimal, sum_money


class InvoiceBuilder:
    def build(self, events: Iterable[BillableEvent], *, invoice_id: str) -> dict:
        items = list(events)
        totals: dict[str, list[Decimal]] = defaultdict(list)
        for item in items:
            totals[item.currency].append(
                money_decimal(item.amount, name="billable_event_amount")
            )
        return {
            "invoice_id": invoice_id,
            "line_count": len(items),
            "totals": {
                currency: legacy_float(
                    sum_money(tuple(amounts)),
                    name=f"invoice_total[{currency}]",
                )
                for currency, amounts in totals.items()
            },
            "items": [item.__dict__.copy() for item in items],
        }
