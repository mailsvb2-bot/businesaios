from __future__ import annotations

from ..contracts import AuditRecord


def evaluate_decision_risk(record: AuditRecord) -> float:
    return record.risk_score
