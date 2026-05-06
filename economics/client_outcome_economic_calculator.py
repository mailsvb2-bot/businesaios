from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from economics.client_outcome_economic_snapshot import ClientOutcomeEconomicSnapshot
from lead_outcomes.client_outcome_contract import BillableClientRecord

CANON_CLIENT_OUTCOME_ECONOMIC_CALCULATOR = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeEconomicCalculator:
    def calculate(self, *, tenant_id: str, business_id: str, order_id: str, package_id: str, verified_clients: int, billable_records: Iterable[BillableClientRecord], acquisition_cost: float, currency: str) -> ClientOutcomeEconomicSnapshot:
        records = tuple(billable_records)
        billable_clients = sum(int(item.quantity) for item in records)
        billed_revenue = round(sum(float(item.amount) for item in records), 2)
        cost = round(max(0.0, float(acquisition_cost)), 2)
        gross_margin = round(billed_revenue - cost, 2)
        cac = round(cost / billable_clients, 2) if billable_clients > 0 else 0.0
        revenue_per_client = round(billed_revenue / billable_clients, 2) if billable_clients > 0 else 0.0
        margin_per_client = round(gross_margin / billable_clients, 2) if billable_clients > 0 else 0.0
        return ClientOutcomeEconomicSnapshot(tenant_id=tenant_id, business_id=business_id, order_id=order_id, package_id=package_id, verified_clients=max(0, int(verified_clients)), billable_clients=billable_clients, billed_revenue=billed_revenue, acquisition_cost=cost, gross_margin=gross_margin, cac=cac, revenue_per_client=revenue_per_client, margin_per_client=margin_per_client, currency=str(currency or 'EUR').upper())
