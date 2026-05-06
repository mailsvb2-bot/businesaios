from __future__ import annotations

from reliability.execution_checkpoint_store import ExecutionCheckpoint, InMemoryExecutionCheckpointStore
from reliability.execution_reconciliation import ExecutionReconciliation
from reliability.idempotency_contract import IdempotencyKey
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage


def test_reconciliation_detects_completed_checkpoint_without_completed_idempotency() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()

    key = IdempotencyKey(
        tenant_id="tenant-1",
        namespace="runtime",
        operation="execute",
        key="run-1",
        scope_hash="scope-1",
    )
    idempotency.reserve(key=key, owner_id="owner-a")
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id="tenant-1",
            run_id="run-1",
            sequence_no=1,
            stage="completed",
            checkpoint_id="cp-1",
            outbox_message_id="msg-1",
        )
    )
    outbox.enqueue(
        OutboxMessage(
            tenant_id="tenant-1",
            message_id="msg-1",
            topic="effects",
            dedupe_key="d-1",
            payload={"ok": True},
        )
    )

    report = ExecutionReconciliation(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    ).reconcile(tenant_id="tenant-1", run_id="run-1", idempotency_key=key, outbox_message_id="msg-1")

    assert "completed_checkpoint_but_idempotency_not_completed" in report.anomalies
    assert "completed_checkpoint_but_outbox_not_delivered" in report.anomalies
