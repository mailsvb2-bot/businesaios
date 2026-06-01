from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRecord:
    decision_id: str
    risk_score: float
    status: str

@dataclass(frozen=True)
class RestrictionProposal:
    decision_id: str
    reason: str
    restrict: bool
