from __future__ import annotations

from dataclasses import dataclass


CANON_ECONOMIC_TRUTH_FRAGMENT = True


@dataclass(frozen=True, slots=True)
class TruthFragment:
    tenant_id: str
    business_id: str
    domain: str
    entity_id: str
    commercial_status: str
    lifecycle_stages: tuple[str, ...]
    booked_amount_minor: int | None
    corrected_amount_minor: int | None
    currency: str | None
    cost_total_minor: int | None = None
    unit_cost_minor: int | None = None
    aggregation_mode: str = 'financial_primary'
    issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    ready_for_export: bool = False
