from __future__ import annotations

from dataclasses import dataclass, field

from infra.audit_log_service import AuditLogService
from infra.decision_ledger import DecisionLedger, DecisionLedgerEntry
from infra.rollback_record import RollbackRecord


@dataclass
class RollbackService:
    audit_log: AuditLogService
    ledger: DecisionLedger
    _records: list[RollbackRecord] = field(default_factory=list)

    def record(self, rollback: RollbackRecord) -> None:
        self._records.append(rollback)
        self.audit_log.record(
            event_name="rollback_recorded",
            actor=rollback.actor,
            category="rollback",
            payload={
                "rollback_id": rollback.rollback_id,
                "target_name": rollback.target_name,
                "reason": rollback.reason,
                "policy_version_id": rollback.policy_version_id,
            },
        )
        self.ledger.append(
            DecisionLedgerEntry(
                entry_id=rollback.rollback_id,
                decision_name="rollback",
                actor=rollback.actor,
                status="recorded",
                policy_version_id=rollback.policy_version_id,
                approval_request_id=None,
                metadata={
                    "target_name": rollback.target_name,
                    "reason": rollback.reason,
                    **dict(rollback.metadata),
                },
            )
        )

    def records(self) -> tuple[RollbackRecord, ...]:
        return tuple(self._records)
