from __future__ import annotations

"""Fail-closed recovery snapshot reconstruction service."""

from datetime import datetime

from reliability.execution_checkpoint_store import ExecutionCheckpointStore
from reliability.execution_reconciliation import ExecutionReconciliation
from reliability.idempotency_contract import IdempotencyKey, IdempotencyStore
from reliability.outbox_store import OutboxStore
from reliability.recovery_execution_graph import (
    RecoveryExecutionGraph,
    build_canonical_recovery_execution_graph,
)
from reliability.recovery_run_rebuilder_analysis import rebuild_facts
from reliability.recovery_run_rebuilder_model import (
    _RecoverySnapshot,
    _checkpoint_ids,
    _single,
    RebuiltRunFacts,
)

class RecoveryRunRebuilder:
    def __init__(
        self,
        *,
        checkpoint_store: ExecutionCheckpointStore,
        idempotency_store: IdempotencyStore,
        outbox_store: OutboxStore,
        execution_graph: RecoveryExecutionGraph | None = None,
        required_outbox_stages: tuple[str, ...] = (
            "execution",
            "verification",
            "state_update",
            "evidence",
        ),
    ) -> None:
        self._checkpoints = checkpoint_store
        self._idempotency = idempotency_store
        self._outbox = outbox_store
        self._graph = execution_graph or build_canonical_recovery_execution_graph()
        self._required_outbox_stages = tuple(
            dict.fromkeys(
                self._graph.require_stage(stage)
                for stage in required_outbox_stages
            )
        )
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
        observed_at: datetime | None = None,
    ) -> RebuiltRunFacts:
        return rebuild_facts(
            self,
            tenant_id=tenant_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            outbox_message_id=outbox_message_id,
            observed_at=observed_at,
        )

    def _snapshot(
        self,
        *,
        tenant: str,
        run: str,
        idempotency_key: IdempotencyKey | None,
        requested_outbox_id: str | None,
    ) -> _RecoverySnapshot:
        checkpoints = tuple(
            self._checkpoints.list_run(tenant_id=tenant, run_id=run)
        )
        outbox_ids = _checkpoint_ids(checkpoints, "outbox_message_id")
        idempotency_keys = _checkpoint_ids(checkpoints, "idempotency_key")
        trace_ids = _checkpoint_ids(checkpoints, "trace_id")
        decision_ids = _checkpoint_ids(checkpoints, "decision_id")
        canonical_outbox_id = _single(outbox_ids)
        canonical_idempotency_key = _single(idempotency_keys)
        resolved_outbox_id = (
            None
            if len(outbox_ids) > 1
            else canonical_outbox_id or requested_outbox_id
        )
        idempotency_record = (
            None
            if idempotency_key is None
            else self._idempotency.get(key=idempotency_key)
        )
        outbox_message = (
            None
            if resolved_outbox_id is None
            else self._outbox.get(
                tenant_id=tenant,
                message_id=resolved_outbox_id,
            )
        )
        return _RecoverySnapshot(
            checkpoints=checkpoints,
            idempotency_record=idempotency_record,
            outbox_message=outbox_message,
            outbox_ids=outbox_ids,
            idempotency_keys=idempotency_keys,
            trace_ids=trace_ids,
            decision_ids=decision_ids,
            canonical_outbox_id=canonical_outbox_id,
            canonical_idempotency_key=canonical_idempotency_key,
            resolved_outbox_id=resolved_outbox_id,
        )



__all__ = ["RecoveryRunRebuilder"]
