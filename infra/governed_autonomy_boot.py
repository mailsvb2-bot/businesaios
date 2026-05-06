from __future__ import annotations

from dataclasses import dataclass

from infra.approval_service import ApprovalService
from infra.approval_store import InMemoryApprovalStore
from infra.audit_log_service import AuditLogService
from infra.decision_ledger import DecisionLedger
from infra.governed_autonomy_boot_result import GovernedAutonomyBootResult
from infra.policy_versioning import PolicyVersionRegistry
from infra.release_promotion import ReleasePromotionService
from infra.rollback_service import RollbackService


@dataclass
class GovernedAutonomyBoot:
    audit_log: AuditLogService

    def build(self) -> GovernedAutonomyBootResult:
        ledger = DecisionLedger()
        approvals = ApprovalService(
            store=InMemoryApprovalStore(),
            audit_log=self.audit_log,
        )
        policy_versions = PolicyVersionRegistry()
        release_promotions = ReleasePromotionService(
            audit_log=self.audit_log,
            ledger=ledger,
        )
        rollbacks = RollbackService(
            audit_log=self.audit_log,
            ledger=ledger,
        )

        self.audit_log.record(
            event_name="governed_autonomy_boot_completed",
            actor="system",
            category="governed_autonomy_boot",
            payload={},
        )

        return GovernedAutonomyBootResult(
            approvals=approvals,
            policy_versions=policy_versions,
            decision_ledger=ledger,
            release_promotions=release_promotions,
            rollbacks=rollbacks,
        )
