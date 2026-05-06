from __future__ import annotations

from dataclasses import dataclass

from infra.audit_log_service import AuditLogService
from infra.change_management import ChangeManagementService
from infra.incident_mode import IncidentMode
from infra.operator_actions import OperatorActionsService


@dataclass(frozen=True)
class ComplianceBootResult:
    audit_log: AuditLogService
    change_management: ChangeManagementService
    operator_actions: OperatorActionsService
    incident_mode: IncidentMode
