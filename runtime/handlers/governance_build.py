from __future__ import annotations
CANON_THIN_HANDLER = True
from runtime.governance import AuditRecord, build_audit_record

def handle_governance_build(decision_id: str, risk_score: float, status: str) -> AuditRecord:
    return build_audit_record(decision_id=decision_id, risk_score=risk_score, status=status)
