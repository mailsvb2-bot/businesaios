from __future__ import annotations
from .contracts import AuditRecord, RestrictionProposal

def build_restriction_proposal(record: AuditRecord) -> RestrictionProposal:
    return RestrictionProposal(decision_id=record.decision_id, reason=f"risk:{record.risk_score}", restrict=record.risk_score > 0.8)
