from __future__ import annotations

from dataclasses import dataclass


CANON_ECONOMIC_BILLABLE_FACT = True


@dataclass(frozen=True, slots=True)
class BillableFact:
    tenant_id: str
    business_id: str
    domain: str
    entity_id: str
    amount_minor: int
    currency: str
    reason_code: str
    evidence_refs: tuple[str, ...] = ()
    idempotency_key: str = ''
