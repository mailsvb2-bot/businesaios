"""Governance evaluate handler.

Evaluates governance risk and returns a deterministic restriction proposal.
"""

from __future__ import annotations

from runtime.governance import AuditRecord, build_restriction_proposal

CANON_THIN_HANDLER = True


def handle_governance_evaluate(*, decision_id: str, context: object) -> dict:
    risk_score = 0.0
    status = "unknown"
    if isinstance(context, AuditRecord):
        risk_score = float(context.risk_score)
        status = str(context.status)
    elif isinstance(context, dict):
        risk_score = float(context.get("risk_score", 0.0) or 0.0)
        status = str(context.get("status", "unknown") or "unknown")
    else:
        if hasattr(context, "risk_score"):
            risk_score = float(getattr(context, "risk_score", 0.0) or 0.0)
        if hasattr(context, "status"):
            status = str(getattr(context, "status", "unknown") or "unknown")

    record = AuditRecord(decision_id=str(decision_id), risk_score=risk_score, status=status)
    proposal = build_restriction_proposal(record)
    return {
        "ok": True,
        "decision_id": proposal.decision_id,
        "restrict": bool(proposal.restrict),
        "reason": str(proposal.reason),
        "status": str(status),
        "risk_score": float(risk_score),
    }
