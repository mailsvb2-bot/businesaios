from __future__ import annotations

from dataclasses import dataclass

from infra.approval_service import ApprovalService
from infra.decision_ledger import DecisionLedger
from infra.policy_versioning import PolicyVersionRegistry
from infra.release_promotion import ReleasePromotionService
from infra.rollback_service import RollbackService


@dataclass(frozen=True)
class GovernedAutonomyBootResult:
    approvals: ApprovalService
    policy_versions: PolicyVersionRegistry
    decision_ledger: DecisionLedger
    release_promotions: ReleasePromotionService
    rollbacks: RollbackService
