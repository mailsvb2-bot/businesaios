from __future__ import annotations

from dataclasses import dataclass

CANON_ECONOMIC_CORRECTION_FACT = True


@dataclass(frozen=True, slots=True)
class CorrectionFact:
    tenant_id: str
    business_id: str
    domain: str
    original_entity_id: str
    correction_type: str
    amount_minor: int
    currency: str
    reason_code: str
    evidence_refs: tuple[str, ...] = ()
