from __future__ import annotations

from infra.governed_autonomy_boot_result import GovernedAutonomyBootResult
from infra.rollback_record import RollbackRecord


def example_rollback(
    governed: GovernedAutonomyBootResult,
) -> dict:
    governed.rollbacks.record(
        RollbackRecord(
            rollback_id="rb-001",
            actor="operator:bob",
            target_name="release-2026-03-11",
            reason="conversion_drop_detected",
            policy_version_id="policy-v1",
            metadata={"severity": "high"},
        )
    )

    return {
        "rollback_records": len(governed.rollbacks.records()),
        "ledger_entries": len(governed.decision_ledger.entries()),
    }
