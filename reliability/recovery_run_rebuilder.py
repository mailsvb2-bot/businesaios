from __future__ import annotations

"""Recovery run rebuilder.

Reconstructs durable run facts from:
- checkpoints
- idempotency state
- outbox state
- canonical topology validation

Important:
- infra-only
- no business decision making
- no second brain
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from reliability.execution_checkpoint_store import ExecutionCheckpoint, ExecutionCheckpointStore
from reliability.execution_reconciliation import ExecutionReconciliation, ReconciliationReport
from reliability.idempotency_contract import (
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyState,
    IdempotencyStore,
)
from reliability.outbox_store import OutboxMessage, OutboxState, OutboxStore
from reliability.recovery_execution_graph import (
    RecoveryExecutionGraph,
    RecoveryGraphValidationReport,
    RecoveryResumePoint,
    build_canonical_recovery_execution_graph,
)


CANON_RECOVERY_RUN_REBUILDER = True


@dataclass(frozen=True)
class RebuiltRunFacts:
    tenant_id: str
    run_id: str
    latest_stage: str | None
    latest_checkpoint: ExecutionCheckpoint | None
    checkpoints: tuple[ExecutionCheckpoint, ...] = field(default_factory=tuple)

    idempotency_record: IdempotencyRecord | None = None
    outbox_message: OutboxMessage | None = None

    graph_validation: RecoveryGraphValidationReport = field(
        default_factory=lambda: RecoveryGraphValidationReport(
            is_valid=True,
            latest_stage=None,
        )
    )
    reconciliation: ReconciliationReport = field(
        default_factory=lambda: ReconciliationReport(
            run_id="",
            latest_stage=None,
            idempotency_state=None,
            outbox_state=None,
            checkpoint_count=0,
            anomalies=(),
        )
    )
    resume_point: RecoveryResumePoint = field(
        default_factory=lambda: RecoveryResumePoint(
            action="restart_from_scratch",
            stage="request",
            reason="default",
        )
    )

    anomalies: tuple[str, ...] = field(default_factory=tuple)
    derived_flags: Mapping[str, Any] = field(default_factory=dict)
    canonical_outbox_message_id: str | None = None
    canonical_idempotency_key: str | None = None
    partial_history_detected: bool = False

    @property
    def checkpoint_count(self) -> int:
        return len(self.checkpoints)

    @property
    def is_terminal(self) -> bool:
        return self.latest_stage in {"completed", "failed"}

    @property
    def is_clean(self) -> bool:
        return not self.anomalies

    @property
    def idempotency_state(self) -> str | None:
        if self.idempotency_record is None:
            return None
        return self.idempotency_record.state.value

    @property
    def outbox_state(self) -> str | None:
        if self.outbox_message is None:
            return None
        return self.outbox_message.state.value

    @property
    def has_live_idempotency_lease(self) -> bool:
        record = self.idempotency_record
        return bool(
            record is not None
            and record.state is IdempotencyState.IN_PROGRESS
            and record.has_live_lease()
        )

    @property
    def idempotency_is_terminal(self) -> bool:
        record = self.idempotency_record
        return bool(
            record is not None
            and record.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED}
        )

    @property
    def outbox_is_claimable(self) -> bool:
        message = self.outbox_message
        return bool(message is not None and message.is_claimable())

    @property
    def outbox_is_delivered(self) -> bool:
        message = self.outbox_message
        return bool(message is not None and message.state is OutboxState.DELIVERED)

    @property
    def outbox_is_dead(self) -> bool:
        message = self.outbox_message
        return bool(message is not None and message.state is OutboxState.DEAD)


class RecoveryRunRebuilder:
    def __init__(
        self,
        *,
        checkpoint_store: ExecutionCheckpointStore,
        idempotency_store: IdempotencyStore,
        outbox_store: OutboxStore,
        execution_graph: RecoveryExecutionGraph | None = None,
        required_outbox_stages: tuple[str, ...] = ("execution", "verification", "state_update", "evidence"),
    ) -> None:
        self._checkpoints = checkpoint_store
        self._idempotency = idempotency_store
        self._outbox = outbox_store
        self._graph = execution_graph or build_canonical_recovery_execution_graph()
        self._required_outbox_stages = tuple(required_outbox_stages)
        self._reconciliation = ExecutionReconciliation(
            checkpoint_store=checkpoint_store,
            idempotency_store=idempotency_store,
            outbox_store=outbox_store,
        )

    def rebuild(
        self,
        *,
        tenant_id: str,
        run_id: str,
        idempotency_key: IdempotencyKey | None = None,
        outbox_message_id: str | None = None,
    ) -> RebuiltRunFacts:
        checkpoints = self._checkpoints.list_run(tenant_id=tenant_id, run_id=run_id)
        latest_checkpoint = checkpoints[-1] if checkpoints else None

        idempotency_record = None
        if idempotency_key is not None:
            idempotency_record = self._idempotency.get(key=idempotency_key)

        outbox_message = None
        if outbox_message_id is not None:
            outbox_message = self._outbox.get(
                tenant_id=tenant_id,
                message_id=outbox_message_id,
            )

        graph_validation = self._graph.validate_run(checkpoints)
        reconciliation = self._reconciliation.reconcile(
            tenant_id=tenant_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            outbox_message_id=outbox_message_id,
        )

        latest_stage = None if latest_checkpoint is None else latest_checkpoint.stage
        resume_point = self._graph.safe_resume_point(latest_stage)

        anomalies: list[str] = []
        anomalies.extend(graph_validation.anomalies)
        anomalies.extend(reconciliation.anomalies)

        checkpoint_outbox_ids = {
            str(item.outbox_message_id)
            for item in checkpoints
            if item.outbox_message_id is not None and str(item.outbox_message_id).strip()
        }
        checkpoint_idempotency_keys = {
            str(item.idempotency_key)
            for item in checkpoints
            if item.idempotency_key is not None and str(item.idempotency_key).strip()
        }
        checkpoint_trace_ids = {
            str(item.trace_id)
            for item in checkpoints
            if item.trace_id is not None and str(item.trace_id).strip()
        }
        checkpoint_decision_ids = {
            str(item.decision_id)
            for item in checkpoints
            if item.decision_id is not None and str(item.decision_id).strip()
        }

        canonical_outbox_message_id = None
        if len(checkpoint_outbox_ids) == 1:
            canonical_outbox_message_id = next(iter(checkpoint_outbox_ids))
        elif len(checkpoint_outbox_ids) > 1:
            anomalies.append("multiple_outbox_message_ids_in_single_run")

        canonical_idempotency_key = None
        if len(checkpoint_idempotency_keys) == 1:
            canonical_idempotency_key = next(iter(checkpoint_idempotency_keys))
        elif len(checkpoint_idempotency_keys) > 1:
            anomalies.append("multiple_idempotency_keys_in_single_run")

        if len(checkpoint_trace_ids) > 1:
            anomalies.append("multiple_trace_ids_in_single_run")
        if len(checkpoint_decision_ids) > 1:
            anomalies.append("multiple_decision_ids_in_single_run")

        if outbox_message_id is not None and canonical_outbox_message_id is not None and str(outbox_message_id) != canonical_outbox_message_id:
            anomalies.append("requested_outbox_message_id_mismatch")

        if latest_checkpoint is not None and latest_checkpoint.outbox_message_id and outbox_message_id:
            if str(latest_checkpoint.outbox_message_id) != str(outbox_message_id):
                anomalies.append("latest_checkpoint_outbox_message_id_mismatch")

        if idempotency_key is not None and canonical_idempotency_key is not None and str(idempotency_key.key) != canonical_idempotency_key:
            anomalies.append("requested_idempotency_key_mismatch")

        if latest_checkpoint is not None and latest_checkpoint.idempotency_key and idempotency_key is not None:
            if str(latest_checkpoint.idempotency_key) != str(idempotency_key.key):
                anomalies.append("latest_checkpoint_idempotency_key_mismatch")

        if outbox_message_id is not None and outbox_message is None:
            anomalies.append("outbox_message_id_provided_but_missing")

        if idempotency_key is not None and idempotency_record is None:
            if latest_stage in {"execution", "verification", "state_update", "evidence", "completed", "failed"}:
                anomalies.append("late_run_without_idempotency_record")

        if outbox_message is not None:
            if latest_checkpoint is None:
                anomalies.append("outbox_exists_without_checkpoints")
            if outbox_message.run_id is not None and str(outbox_message.run_id) != str(run_id):
                anomalies.append("outbox_run_id_mismatch")
            if outbox_message.tenant_id != str(tenant_id):
                anomalies.append("outbox_tenant_id_mismatch")
            if outbox_message.state is OutboxState.DELIVERED and outbox_message.delivered_at is None:
                anomalies.append("delivered_outbox_missing_delivered_at")
            if outbox_message.state is OutboxState.DEAD and not str(outbox_message.last_error or "").strip():
                anomalies.append("dead_outbox_missing_last_error")

        if idempotency_record is not None:
            if idempotency_record.idempotency_key.tenant_id != str(tenant_id):
                anomalies.append("idempotency_tenant_id_mismatch")
            if latest_checkpoint is None and idempotency_record.state in {
                IdempotencyState.IN_PROGRESS,
                IdempotencyState.COMPLETED,
                IdempotencyState.FAILED,
            }:
                anomalies.append("idempotency_exists_without_checkpoints")
            if idempotency_record.state is IdempotencyState.COMPLETED and idempotency_record.completed_at is None:
                anomalies.append("completed_idempotency_missing_completed_at")
            if idempotency_record.state is IdempotencyState.IN_PROGRESS and not idempotency_record.has_live_lease() and latest_stage in {"execution", "verification", "state_update", "evidence"}:
                anomalies.append("late_run_with_expired_idempotency_lease")

        if latest_checkpoint is not None:
            if latest_stage in self._required_outbox_stages and outbox_message_id is None and canonical_outbox_message_id is None:
                anomalies.append("late_stage_without_outbox_message_id_input")
            if latest_stage in self._required_outbox_stages and not checkpoint_outbox_ids and outbox_message is None:
                anomalies.append("late_stage_without_any_outbox_reference")
            if latest_stage in {"decision", "executable_action", *self._required_outbox_stages, "completed", "failed"} and idempotency_key is None and canonical_idempotency_key is None:
                anomalies.append("late_stage_without_any_idempotency_reference")

            if latest_stage == "completed":
                if idempotency_record is not None and idempotency_record.state is not IdempotencyState.COMPLETED:
                    anomalies.append("completed_run_without_completed_idempotency")
                if outbox_message is not None and outbox_message.state is not OutboxState.DELIVERED:
                    anomalies.append("completed_run_without_delivered_outbox")
                if outbox_message is not None and outbox_message.is_claimable():
                    anomalies.append("completed_run_with_claimable_outbox")

            if latest_stage == "failed":
                if idempotency_record is not None and idempotency_record.state is IdempotencyState.COMPLETED:
                    anomalies.append("failed_run_with_completed_idempotency")
                if outbox_message is not None and outbox_message.state is OutboxState.DELIVERED:
                    anomalies.append("failed_run_with_delivered_outbox")

        if outbox_message is not None and outbox_message.state is OutboxState.DELIVERED:
            if latest_stage in {None, "request", "world_state", "decision"}:
                anomalies.append("delivered_outbox_before_late_execution_stage")

        if idempotency_record is not None and idempotency_record.state is IdempotencyState.FAILED:
            if latest_stage == "completed":
                anomalies.append("idempotency_failed_but_run_completed")

        if idempotency_record is not None and idempotency_record.state is IdempotencyState.COMPLETED:
            if latest_stage == "failed":
                anomalies.append("idempotency_completed_but_run_failed")

        partial_history_detected = graph_validation.inferred_entry_stage is not None

        derived_flags = {
            "graph_is_valid": graph_validation.is_valid,
            "graph_can_resume": graph_validation.can_resume,
            "partial_history_detected": partial_history_detected,
            "inferred_entry_stage": graph_validation.inferred_entry_stage,
            "skipped_forward_stages": list(graph_validation.skipped_forward_stages),
            "resume_action": resume_point.action,
            "resume_stage": resume_point.stage,
            "resume_reason": resume_point.reason,
            "has_live_idempotency_lease": bool(
                idempotency_record is not None
                and idempotency_record.state is IdempotencyState.IN_PROGRESS
                and idempotency_record.has_live_lease()
            ),
            "idempotency_terminal": bool(
                idempotency_record is not None
                and idempotency_record.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED}
            ),
            "outbox_claimable": bool(outbox_message is not None and outbox_message.is_claimable()),
            "outbox_delivered": bool(outbox_message is not None and outbox_message.state is OutboxState.DELIVERED),
            "outbox_dead": bool(outbox_message is not None and outbox_message.state is OutboxState.DEAD),
            "run_terminal": bool(latest_stage in {"completed", "failed"}),
            "cross_store_consistent": not anomalies,
            "claimable_outbox_while_idempotency_lease_live": bool(outbox_message is not None and outbox_message.is_claimable() and idempotency_record is not None and idempotency_record.has_live_lease()) if idempotency_record is not None else False,
        }

        return RebuiltRunFacts(
            tenant_id=str(tenant_id),
            run_id=str(run_id),
            latest_stage=latest_stage,
            latest_checkpoint=latest_checkpoint,
            checkpoints=tuple(checkpoints),
            idempotency_record=idempotency_record,
            outbox_message=outbox_message,
            graph_validation=graph_validation,
            reconciliation=reconciliation,
            resume_point=resume_point,
            anomalies=tuple(dict.fromkeys(anomalies)),
            derived_flags=derived_flags,
            canonical_outbox_message_id=canonical_outbox_message_id,
            canonical_idempotency_key=canonical_idempotency_key,
            partial_history_detected=partial_history_detected,
        )


__all__ = [
    "CANON_RECOVERY_RUN_REBUILDER",
    "RebuiltRunFacts",
    "RecoveryRunRebuilder",
]
