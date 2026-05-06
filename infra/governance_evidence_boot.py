from __future__ import annotations

from dataclasses import dataclass

from infra.audit_log_service import AuditLogService
from infra.governance_evidence_boot_result import GovernanceEvidenceBootResult
from infra.governance_evidence_service import GovernanceEvidenceService
from infra.operator_session_records import OperatorSessionRegistry


@dataclass
class GovernanceEvidenceBoot:
    audit_log: AuditLogService

    def build(self) -> GovernanceEvidenceBootResult:
        sessions = OperatorSessionRegistry()
        service = GovernanceEvidenceService(
            audit_log=self.audit_log,
            sessions=sessions,
        )

        self.audit_log.record(
            event_name="governance_evidence_boot_completed",
            actor="system",
            category="governance_evidence_boot",
            payload={},
        )

        return GovernanceEvidenceBootResult(
            sessions=sessions,
            service=service,
        )
