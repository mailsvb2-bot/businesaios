from __future__ import annotations
from ..contracts import AuditRecord

def explain_decision_audit(record: AuditRecord) -> str:
    return f"decision_id={record.decision_id}; risk_score={record.risk_score}; status={record.status}"
