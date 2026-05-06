from __future__ import annotations

from dataclasses import dataclass, field

from infra.audit_log_service import AuditLogService
from infra.decision_ledger import DecisionLedger, DecisionLedgerEntry


@dataclass(frozen=True)
class ReleasePromotionRequest:
    promotion_id: str
    actor: str
    release_name: str
    target_stage: str
    policy_version_id: str | None = None
    approval_request_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReleasePromotionService:
    audit_log: AuditLogService
    ledger: DecisionLedger

    def promote(self, request: ReleasePromotionRequest) -> None:
        self.audit_log.record(
            event_name="release_promoted",
            actor=request.actor,
            category="release_promotion",
            payload={
                "promotion_id": request.promotion_id,
                "release_name": request.release_name,
                "target_stage": request.target_stage,
                "policy_version_id": request.policy_version_id,
                "approval_request_id": request.approval_request_id,
            },
        )
        self.ledger.append(
            DecisionLedgerEntry(
                entry_id=request.promotion_id,
                decision_name="release_promotion",
                actor=request.actor,
                status="promoted",
                policy_version_id=request.policy_version_id,
                approval_request_id=request.approval_request_id,
                metadata={
                    "release_name": request.release_name,
                    "target_stage": request.target_stage,
                    **dict(request.metadata),
                },
            )
        )
