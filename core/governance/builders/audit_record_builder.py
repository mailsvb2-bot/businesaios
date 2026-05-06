from __future__ import annotations
from ..contracts import AuditRecord

def build_audit_record(decision_id: str, risk_score: float, status: str) -> AuditRecord:
    return AuditRecord(decision_id=decision_id, risk_score=risk_score, status=status)
