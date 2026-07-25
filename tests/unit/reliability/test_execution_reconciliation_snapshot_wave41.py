from __future__ import annotations

from reliability.execution_reconciliation import ExecutionReconciliation
from reliability.idempotency_contract import IdempotencyState
from reliability.outbox_store import OutboxState
from tests.unit.reliability.recovery_run_wave41_support import (
    KEY,
    OUTBOX_ID,
    RUN,
    TENANT,
    SequenceCheckpointStore,
    SequenceIdempotencyStore,
    SequenceOutboxStore,
    checkpoint,
    idempotency_record,
    outbox_message,
    path_to,
)


def subject(checkpoints=(), idem=None, outbox=None):
    return ExecutionReconciliation(
        checkpoint_store=SequenceCheckpointStore(checkpoints),
        idempotency_store=SequenceIdempotencyStore(idem),
        outbox_store=SequenceOutboxStore(outbox),
    )


def test_reconcile_wrapper_handles_optional_and_explicit_records() -> None:
    empty = subject().reconcile(tenant_id=TENANT, run_id=RUN)
    assert empty.is_clean
    assert empty.latest_stage is None
    assert empty.idempotency_state is None
    assert empty.outbox_state is None

    completed = subject(
        path_to("completed"),
        idempotency_record(IdempotencyState.COMPLETED),
        outbox_message(OutboxState.DELIVERED),
    ).reconcile(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        outbox_message_id=OUTBOX_ID,
    )
    assert completed.is_clean
    assert completed.latest_stage == "completed"
    assert completed.idempotency_state == "completed"
    assert completed.outbox_state == "delivered"


def test_snapshot_detects_checkpoint_sequence_anomalies() -> None:
    valid_repeat = (
        checkpoint("request", 0, checkpoint_id="same"),
        checkpoint("request", 1, checkpoint_id="same"),
    )
    report = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=valid_repeat,
        idempotency_record=None,
        outbox_message=None,
    )
    assert report.is_clean

    invalid_repeat = (
        checkpoint("request", 0, checkpoint_id="same"),
        checkpoint(
            "world_state",
            1,
            checkpoint_id="same",
        ),
    )
    report = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=invalid_repeat,
        idempotency_record=None,
        outbox_message=None,
    )
    assert report.anomalies == ("duplicate_checkpoint_id",)

    non_monotonic = (
        checkpoint("request", 2),
        checkpoint("world_state", 1),
    )
    report = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=non_monotonic,
        idempotency_record=None,
        outbox_message=None,
    )
    assert report.anomalies == ("non_monotonic_sequence",)


def test_snapshot_cross_store_terminal_and_delivery_anomalies() -> None:
    completed = path_to("completed")
    report = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=completed,
        idempotency_record=idempotency_record(IdempotencyState.IN_PROGRESS),
        outbox_message=outbox_message(OutboxState.PENDING),
    )
    assert "completed_checkpoint_but_idempotency_not_completed" in report.anomalies
    assert "completed_checkpoint_but_outbox_not_delivered" in report.anomalies

    late = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=path_to("execution"),
        idempotency_record=None,
        outbox_message=None,
    )
    assert "late_stage_without_outbox_record" in late.anomalies

    failed = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=path_to("failed"),
        idempotency_record=idempotency_record(IdempotencyState.COMPLETED),
        outbox_message=None,
    )
    assert "idempotency_completed_but_checkpoint_failed" in failed.anomalies

    completed_failed_idem = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=completed,
        idempotency_record=idempotency_record(IdempotencyState.FAILED),
        outbox_message=outbox_message(OutboxState.DELIVERED),
    )
    assert "idempotency_failed_but_checkpoint_completed" in (
        completed_failed_idem.anomalies
    )

    early_delivery = subject().reconcile_snapshot(
        run_id=RUN,
        checkpoints=(checkpoint("request", 0),),
        idempotency_record=None,
        outbox_message=outbox_message(OutboxState.DELIVERED),
    )
    assert "outbox_delivered_before_late_execution_stage" in (
        early_delivery.anomalies
    )
