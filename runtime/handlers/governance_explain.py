from __future__ import annotations
CANON_THIN_HANDLER = True
from runtime.governance import AuditRecord, explain_decision_audit

def handle_governance_explain(record: AuditRecord) -> str:
    return explain_decision_audit(record)
