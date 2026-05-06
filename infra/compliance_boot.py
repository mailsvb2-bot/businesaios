from __future__ import annotations

from dataclasses import dataclass

from infra.audit_log_service import AuditLogService
from infra.audit_sink import InMemoryAuditSink
from infra.change_management import ChangeManagementService
from infra.compliance_boot_result import ComplianceBootResult
from infra.control_plane_boot_result import ControlPlaneBootResult
from infra.incident_mode import IncidentMode
from infra.operator_actions import OperatorActionsService


@dataclass
class ComplianceBoot:
    control_plane: ControlPlaneBootResult

    def build(self) -> ComplianceBootResult:
        audit_log = AuditLogService(
            sink=InMemoryAuditSink(),
        )
        change_management = ChangeManagementService(
            audit_log=audit_log,
        )
        operator_actions = OperatorActionsService(
            feature_flags=self.control_plane.feature_flags,
            kill_switches=self.control_plane.kill_switches,
            maintenance_mode=self.control_plane.maintenance_mode,
            audit_log=audit_log,
        )
        incident_mode = IncidentMode()

        audit_log.record(
            event_name="compliance_boot_completed",
            actor="system",
            category="compliance_boot",
            payload={},
        )

        return ComplianceBootResult(
            audit_log=audit_log,
            change_management=change_management,
            operator_actions=operator_actions,
            incident_mode=incident_mode,
        )
