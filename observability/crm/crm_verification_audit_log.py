from __future__ import annotations

from observability.crm.crm_action_audit_log import CrmActionAuditLog
from observability.crm.crm_audit_event_schema import CrmAuditEvent


class CrmVerificationAuditLog(CrmActionAuditLog):
    """Specialized audit log facade for CRM verification events."""

    def record_verification(self, event: CrmAuditEvent) -> None:
        self.record(event)
