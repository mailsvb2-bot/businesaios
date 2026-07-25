from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from reliability.execution_checkpoint_store import (
    ExecutionCheckpoint,
    ExecutionCheckpointStore,
)
from reliability.idempotency_contract import (
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyState,
    IdempotencyStore,
)
from reliability.outbox_store import OutboxMessage, OutboxState, OutboxStore


CANON_EXECUTION_RECONCILIATION = True


@dataclass(frozen=True)
class ReconciliationReport:
    run_id: str
    latest_stage: str | None
    idempotency_state: str | None
    outbox_state: str | None
    checkpoint_count: int = 0
    anomalies: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.anomalies


class ExecutionReconciliation:
    def __init__(
        self,
        *,
        checkpoint_store: ExecutionCheckpointStore,
        idempotency_store: IdempotencyStore,
        outbox_store: OutboxStore,
    ) -> None:
        self._checkpoints = checkpoint_store
        self._idempotency = idempotency_store
        self._outbox = outbox_store

    def reconcile(
        self,
        *,
        tenant_id: str,
        run_id: str,
        idempotency_key: IdempotencyKey | None = None,
        outbox_message_id: str | None = None,
    ) -> ReconciliationReport:
        checkpoints = self._checkpoints.list_run(
            tenant_id=tenant_id,
            run_id=run_id,
        )
        idempotency_record = (
            None
            if idempotency_key is None
            else self._idempotency.get(key=idempotency_key)
        )
        outbox_message = (
            None
            if outbox_message_id is None
            else self._outbox.get(
                tenant_id=tenant_id,
                message_id=outbox_message_id,
            )
        )
        return self.reconcile_snapshot(
            run_id=run_id,
            checkpoints=checkpoints,
            idempotency_record=idempotency_record,
            outbox_message=outbox_message,
        )

    def reconcile_snapshot(
        self,
        *,
        run_id: str,
        checkpoints: Sequence[ExecutionCheckpoint],
        idempotency_record: IdempotencyRecord | None,
        outbox_message: OutboxMessage | None,
    ) -> ReconciliationReport:
        captured = tuple(checkpoints)
        latest = captured[-1] if captured else None
        anomalies: list[str] = []
        latest_stage = None if latest is None else latest.stage
        idempotency_state = (
            None
            if idempotency_record is None
            else idempotency_record.state.value
        )
        outbox_state = (
            None if outbox_message is None else outbox_message.state.value
        )

        if captured:
            seen_by_id: dict[str, ExecutionCheckpoint] = {}
            last_sequence = -1
            for checkpoint in captured:
                prior = seen_by_id.get(checkpoint.checkpoint_id)
                if prior is not None:
                    same_stage = str(prior.stage) == str(checkpoint.stage)
                    same_decision = str(prior.decision_id or "") == str(
                        checkpoint.decision_id or ""
                    )
                    same_action = str(prior.action_id or "") == str(
                        checkpoint.action_id or ""
                    )
                    valid_repeat = (
                        same_stage
                        and same_decision
                        and same_action
                        and checkpoint.sequence_no > prior.sequence_no
                    )
                    if not valid_repeat:
                        anomalies.append("duplicate_checkpoint_id")
                        break
                seen_by_id[checkpoint.checkpoint_id] = checkpoint
                if checkpoint.sequence_no <= last_sequence:
                    anomalies.append("non_monotonic_sequence")
                    break
                last_sequence = checkpoint.sequence_no

        if latest is not None and latest.stage == "completed":
            if (
                idempotency_record is not None
                and idempotency_record.state is not IdempotencyState.COMPLETED
            ):
                anomalies.append(
                    "completed_checkpoint_but_idempotency_not_completed"
                )
            if (
                outbox_message is not None
                and outbox_message.state is not OutboxState.DELIVERED
            ):
                anomalies.append("completed_checkpoint_but_outbox_not_delivered")

        late_delivery_stages = {
            "execution",
            "verification",
            "state_update",
            "evidence",
        }
        if (
            latest is not None
            and latest.stage in late_delivery_stages
            and outbox_message is None
        ):
            anomalies.append("late_stage_without_outbox_record")

        if (
            idempotency_record is not None
            and idempotency_record.state is IdempotencyState.COMPLETED
            and latest is not None
            and latest.stage == "failed"
        ):
            anomalies.append("idempotency_completed_but_checkpoint_failed")

        if (
            idempotency_record is not None
            and idempotency_record.state is IdempotencyState.FAILED
            and latest is not None
            and latest.stage == "completed"
        ):
            anomalies.append("idempotency_failed_but_checkpoint_completed")

        if (
            outbox_message is not None
            and outbox_message.state is OutboxState.DELIVERED
            and latest is not None
            and latest.stage in {"request", "world_state", "decision"}
        ):
            anomalies.append("outbox_delivered_before_late_execution_stage")

        return ReconciliationReport(
            run_id=str(run_id),
            latest_stage=latest_stage,
            idempotency_state=idempotency_state,
            outbox_state=outbox_state,
            checkpoint_count=len(captured),
            anomalies=tuple(dict.fromkeys(anomalies)),
        )


__all__ = [
    "CANON_EXECUTION_RECONCILIATION",
    "ExecutionReconciliation",
    "ReconciliationReport",
]
