from __future__ import annotations

from dataclasses import dataclass, field

from reliability.execution_checkpoint_store import ExecutionCheckpointStore
from reliability.idempotency_contract import IdempotencyKey, IdempotencyState, IdempotencyStore
from reliability.outbox_store import OutboxState, OutboxStore


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
        checkpoints = self._checkpoints.list_run(tenant_id=tenant_id, run_id=run_id)
        latest = checkpoints[-1] if checkpoints else None
        idem = None if idempotency_key is None else self._idempotency.get(key=idempotency_key)
        outbox = None if outbox_message_id is None else self._outbox.get(tenant_id=tenant_id, message_id=outbox_message_id)

        anomalies: list[str] = []
        latest_stage = None if latest is None else latest.stage
        idem_state = None if idem is None else idem.state.value
        outbox_state = None if outbox is None else outbox.state.value

        if checkpoints:
            seen_by_id: dict[str, ExecutionCheckpoint] = {}
            last_seq = -1
            for checkpoint in checkpoints:
                prior = seen_by_id.get(checkpoint.checkpoint_id)
                if prior is not None:
                    same_stage = str(prior.stage) == str(checkpoint.stage)
                    same_decision = str(prior.decision_id or '') == str(checkpoint.decision_id or '')
                    same_action = str(prior.action_id or '') == str(checkpoint.action_id or '')
                    if not (same_stage and same_decision and same_action and checkpoint.sequence_no > prior.sequence_no):
                        anomalies.append("duplicate_checkpoint_id")
                        break
                seen_by_id[checkpoint.checkpoint_id] = checkpoint
                if checkpoint.sequence_no <= last_seq:
                    anomalies.append("non_monotonic_sequence")
                    break
                last_seq = checkpoint.sequence_no

        if latest is not None and latest.stage == "completed":
            if idem is not None and idem.state is not IdempotencyState.COMPLETED:
                anomalies.append("completed_checkpoint_but_idempotency_not_completed")
            if outbox is not None and outbox.state is not OutboxState.DELIVERED:
                anomalies.append("completed_checkpoint_but_outbox_not_delivered")

        if latest is not None and latest.stage in {"execution", "verification", "state_update", "evidence"} and outbox is None:
            anomalies.append("late_stage_without_outbox_record")

        if idem is not None and idem.state is IdempotencyState.COMPLETED and latest is not None and latest.stage == "failed":
            anomalies.append("idempotency_completed_but_checkpoint_failed")

        if idem is not None and idem.state is IdempotencyState.FAILED and latest is not None and latest.stage == "completed":
            anomalies.append("idempotency_failed_but_checkpoint_completed")

        if outbox is not None and outbox.state is OutboxState.DELIVERED and latest is not None and latest.stage in {"request", "world_state", "decision"}:
            anomalies.append("outbox_delivered_before_late_execution_stage")

        return ReconciliationReport(
            run_id=str(run_id),
            latest_stage=latest_stage,
            idempotency_state=idem_state,
            outbox_state=outbox_state,
            checkpoint_count=len(checkpoints),
            anomalies=tuple(dict.fromkeys(anomalies)),
        )


__all__ = [
    "CANON_EXECUTION_RECONCILIATION",
    "ExecutionReconciliation",
    "ReconciliationReport",
]
