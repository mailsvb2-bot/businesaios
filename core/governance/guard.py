from __future__ import annotations

from .contracts import AuditRecord
from .errors import GovernanceGuardViolation


def require_audit_status(record: AuditRecord) -> None:
    if not record.status:
        raise GovernanceGuardViolation("Audit status must not be empty.")
