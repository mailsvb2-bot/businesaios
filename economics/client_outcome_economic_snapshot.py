from __future__ import annotations

from dataclasses import dataclass

CANON_CLIENT_OUTCOME_ECONOMIC_SNAPSHOT = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeEconomicSnapshot:
    tenant_id: str
    business_id: str
    order_id: str
    package_id: str
    verified_clients: int
    billable_clients: int
    billed_revenue: float
    acquisition_cost: float
    gross_margin: float
    cac: float
    revenue_per_client: float
    margin_per_client: float
    currency: str
    reconciliation_consistent: bool | None = None
    reversal_amount: float | None = None
    final_truth_revenue: float | None = None
    issues: tuple[str, ...] = ()
