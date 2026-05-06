from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from observability.action_audit_log import ActionAuditLog
from observability.decision_audit_log import DecisionAuditLog, build_default_decision_audit_log
from security.audit_redaction_policy import AuditRedactionPolicy


CANON_API_AUDIT_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_AUDIT_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class AuditRouteHandlers:
    action_audit_log: ActionAuditLog = field(default_factory=ActionAuditLog)
    decision_audit_log: DecisionAuditLog = field(default_factory=build_default_decision_audit_log)
    audit_redaction_policy: AuditRedactionPolicy = field(default_factory=AuditRedactionPolicy)

    def list_actions(self, *, trace_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        cap = max(0, min(int(limit), 1000))
        if trace_id:
            records = self.action_audit_log.list_by_trace(trace_id=trace_id, limit=cap)
        else:
            records = list(self.action_audit_log.records[-cap:]) if cap else []
        return {
            'kind': 'action_audit',
            'count': len(records),
            'records': [self.audit_redaction_policy.redact_event_dict(item) for item in records],
        }

    def list_decisions(self, *, trace_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        cap = max(0, min(int(limit), 1000))
        if trace_id:
            records = self.decision_audit_log.list_by_trace(trace_id=trace_id, limit=cap)
        else:
            records = list(self.decision_audit_log.records[-cap:]) if cap else []
        return {
            'kind': 'decision_audit',
            'count': len(records),
            'records': [self.audit_redaction_policy.redact_event_dict(item) for item in records],
        }

    def latest_trace(self, *, trace_id: str) -> dict[str, Any]:
        return {
            'trace_id': str(trace_id),
            'actions': self.list_actions(trace_id=trace_id, limit=200)['records'],
            'decisions': self.list_decisions(trace_id=trace_id, limit=200)['records'],
        }


__all__ = [
    'AuditRouteHandlers',
    'CANON_API_AUDIT_ROUTE_HANDLERS',
]
