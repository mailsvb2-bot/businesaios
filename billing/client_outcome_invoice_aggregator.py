from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from billing.client_outcome_invoice_line import ClientOutcomeInvoiceLine
from lead_outcomes.client_outcome_contract import BillableClientRecord

CANON_CLIENT_OUTCOME_INVOICE_AGGREGATOR = True


def period_key_for_month(now: datetime) -> str:
    return f"{now.year:04d}-{now.month:02d}"


@dataclass(frozen=True, slots=True)
class ClientOutcomeInvoiceAggregator:
    def aggregate(self, *, now: datetime, records: Iterable[BillableClientRecord]) -> tuple[ClientOutcomeInvoiceLine, ...]:
        grouped: dict[tuple[str, str, str, str, float, str], list[BillableClientRecord]] = defaultdict(list)
        for record in records:
            grouped[(record.tenant_id, record.business_id, record.order_id, record.package_id, float(record.unit_price), str(record.currency))].append(record)
        period_key = period_key_for_month(now)
        lines = []
        for (tenant_id, business_id, order_id, package_id, unit_price, currency), items in grouped.items():
            quantity = sum(int(item.quantity) for item in items)
            amount = round(sum(float(item.amount) for item in items), 2)
            lines.append(ClientOutcomeInvoiceLine(
                invoice_line_id=f'invline:{tenant_id}:{order_id}:{package_id}:{period_key}',
                tenant_id=tenant_id,
                business_id=business_id,
                order_id=order_id,
                package_id=package_id,
                period_key=period_key,
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                currency=currency,
                description=f'Verified clients ({quantity}) for package {package_id}',
                generated_at=now,
            ))
        return tuple(sorted(lines, key=lambda item: item.invoice_line_id))
