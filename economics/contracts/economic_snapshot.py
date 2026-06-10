from __future__ import annotations

from dataclasses import dataclass

CANON_ECONOMIC_SNAPSHOT_CONTRACT = True


@dataclass(frozen=True, slots=True)
class EconomicSnapshot:
    tenant_id: str
    business_id: str
    scope_type: str
    scope_id: str
    revenue_booked_minor: int
    revenue_corrected_minor: int
    refund_total_minor: int
    reversal_total_minor: int
    chargeback_total_minor: int
    spend_total_minor: int
    margin_minor: int | None
    cac_minor: int | None
    consistency_status: str
    issues: tuple[str, ...]
    ready_for_export: bool
