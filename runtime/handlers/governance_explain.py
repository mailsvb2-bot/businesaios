from __future__ import annotations

from runtime.governance import AuditRecord, explain_decision_audit

CANON_THIN_HANDLER = True

def handle_governance_explain(record: AuditRecord) -> str:
    return explain_decision_audit(record)
