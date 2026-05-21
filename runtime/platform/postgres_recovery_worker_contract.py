from __future__ import annotations

from dataclasses import dataclass

from runtime.execution.crash_window_recovery_contract import (
    CrashWindowRecoveryAction,
    ExecutionCrashWindowState,
    required_recovery_action,
)


@dataclass(frozen=True)
class PostgresRecoveryQueueItem:
    recovery_id: str
    tenant_id: str
    ledger_id: str
    decision_id: str
    idempotency_key: str
    ledger_marked: bool
    dispatch_claimed: bool
    handler_dispatched: bool
    effect_verified: bool
    queued_action: str
    status: str


def evaluate_recovery_queue_item(item: PostgresRecoveryQueueItem) -> dict[str, object]:
    expected = required_recovery_action(
        ExecutionCrashWindowState(
            decision_id=item.decision_id,
            idempotency_key=item.idempotency_key,
            ledger_marked=item.ledger_marked,
            dispatch_claimed=item.dispatch_claimed,
            handler_dispatched=item.handler_dispatched,
            effect_verified=item.effect_verified,
        )
    ).value
    violations: list[str] = []
    if not item.recovery_id.strip():
        violations.append("recovery_id_required")
    if not item.tenant_id.strip():
        violations.append("tenant_id_required")
    if not item.ledger_id.strip():
        violations.append("ledger_id_required")
    if item.queued_action != expected:
        violations.append("queued_action_mismatch")
    if item.status not in {"pending", "claimed", "verified", "failed"}:
        violations.append("invalid_recovery_status")
    return {
        "artifact": "postgres_recovery_worker_contract",
        "status": "ready" if not violations else "blocked",
        "expected_action": expected,
        "queued_action": item.queued_action,
        "terminal_noop": expected == CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED.value,
        "violations": violations,
        "claims_production_ready": False,
    }


__all__ = ["PostgresRecoveryQueueItem", "evaluate_recovery_queue_item"]
