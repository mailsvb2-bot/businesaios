from __future__ import annotations

from runtime.governance import AuditRecord, build_audit_record

CANON_THIN_HANDLER = True

def handle_governance_build(decision_id: str, risk_score: float, status: str) -> AuditRecord:
    return build_audit_record(decision_id=decision_id, risk_score=risk_score, status=status)
