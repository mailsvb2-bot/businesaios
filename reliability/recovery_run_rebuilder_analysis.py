from __future__ import annotations

"""Passive validation and fact projection for recovery snapshots."""

from datetime import datetime
from typing import Any

from core.tenancy.normalization import require_tenant_id
from reliability.idempotency_contract import IdempotencyKey, IdempotencyState
from reliability.outbox_store import OutboxState
from reliability.recovery_execution_graph import (
    RecoveryGraphValidationReport,
    RecoveryResumePoint,
)
from reliability.recovery_run_rebuilder_model import (
    _LATE_IDEMPOTENCY_STAGES,
    _LATE_LEASE_STAGES,
    _optional_id,
    _require_aware,
    _require_run_id,
    _utc_now,
    RebuiltRunFacts,
)


def rebuild_facts(
    rebuilder: Any,
    *,
    tenant_id: str,
    run_id: str,
    idempotency_key: IdempotencyKey | None = None,
    outbox_message_id: str | None = None,
    observed_at: datetime | None = None,
) -> RebuiltRunFacts:
    tenant = require_tenant_id(tenant_id)
    run = _require_run_id(run_id)
    moment = _require_aware(observed_at or _utc_now())
    requested_outbox_id = _optional_id(
        outbox_message_id,
        "outbox_message_id",
    )
    if idempotency_key is not None:
        idempotency_key.validate()
        if require_tenant_id(idempotency_key.tenant_id) != tenant:
            raise ValueError(
                "idempotency_key tenant_id must match recovery tenant_id"
            )

    first = rebuilder._snapshot(
        tenant=tenant,
        run=run,
        idempotency_key=idempotency_key,
        requested_outbox_id=requested_outbox_id,
    )
    snapshot = rebuilder._snapshot(
        tenant=tenant,
        run=run,
        idempotency_key=idempotency_key,
        requested_outbox_id=requested_outbox_id,
    )
    snapshot_stable = first == snapshot
    checkpoints = snapshot.checkpoints
    latest = checkpoints[-1] if checkpoints else None
    latest_stage = None if latest is None else latest.stage

    try:
        graph_validation = rebuilder._graph.validate_run(checkpoints)
    except (TypeError, ValueError):
        graph_validation = RecoveryGraphValidationReport(
            is_valid=False,
            latest_stage=latest_stage,
            traversed_stages=tuple(item.stage for item in checkpoints),
            anomalies=("checkpoint_validation_error",),
        )
    reconciliation = rebuilder._reconciliation.reconcile_snapshot(
        run_id=run,
        checkpoints=checkpoints,
        idempotency_record=snapshot.idempotency_record,
        outbox_message=snapshot.outbox_message,
    )

    anomalies: list[str] = [
        *graph_validation.anomalies,
        *reconciliation.anomalies,
    ]
    if not snapshot_stable:
        anomalies.append("unstable_recovery_snapshot")

    if any(item.tenant_id != tenant for item in checkpoints):
        anomalies.append("checkpoint_tenant_id_mismatch")
    if any(str(item.run_id) != run for item in checkpoints):
        anomalies.append("checkpoint_run_id_mismatch")
    if len(snapshot.outbox_ids) > 1:
        anomalies.append("multiple_outbox_message_ids_in_single_run")
    if len(snapshot.idempotency_keys) > 1:
        anomalies.append("multiple_idempotency_keys_in_single_run")
    if len(snapshot.trace_ids) > 1:
        anomalies.append("multiple_trace_ids_in_single_run")
    if len(snapshot.decision_ids) > 1:
        anomalies.append("multiple_decision_ids_in_single_run")

    if (
        requested_outbox_id is not None
        and snapshot.canonical_outbox_id is not None
        and requested_outbox_id != snapshot.canonical_outbox_id
    ):
        anomalies.append("requested_outbox_message_id_mismatch")
    if (
        latest is not None
        and latest.outbox_message_id
        and requested_outbox_id
        and str(latest.outbox_message_id).strip() != requested_outbox_id
    ):
        anomalies.append("latest_checkpoint_outbox_message_id_mismatch")
    if (
        idempotency_key is not None
        and snapshot.canonical_idempotency_key is not None
        and str(idempotency_key.key).strip()
        != snapshot.canonical_idempotency_key
    ):
        anomalies.append("requested_idempotency_key_mismatch")
    if (
        latest is not None
        and latest.idempotency_key
        and idempotency_key is not None
        and str(latest.idempotency_key).strip()
        != str(idempotency_key.key).strip()
    ):
        anomalies.append("latest_checkpoint_idempotency_key_mismatch")

    outbox = snapshot.outbox_message
    idempotency = snapshot.idempotency_record
    if (
        requested_outbox_id is not None
        and snapshot.canonical_outbox_id is None
        and outbox is None
    ):
        anomalies.append("outbox_message_id_provided_but_missing")
    if snapshot.canonical_outbox_id is not None and outbox is None:
        anomalies.append("canonical_outbox_message_id_missing")
    if (
        idempotency_key is not None
        and idempotency is None
        and latest_stage in _LATE_IDEMPOTENCY_STAGES
    ):
        anomalies.append("late_run_without_idempotency_record")
    if (
        idempotency_key is None
        and snapshot.canonical_idempotency_key is not None
        and latest_stage in _LATE_IDEMPOTENCY_STAGES
    ):
        anomalies.append(
            "idempotency_record_unresolved_from_checkpoint_reference"
        )

    if outbox is not None:
        if latest is None:
            anomalies.append("outbox_exists_without_checkpoints")
        if str(outbox.message_id).strip() != str(snapshot.resolved_outbox_id):
            anomalies.append("outbox_message_id_mismatch")
        if outbox.run_id is not None and str(outbox.run_id) != run:
            anomalies.append("outbox_run_id_mismatch")
        if outbox.tenant_id != tenant:
            anomalies.append("outbox_tenant_id_mismatch")
        if (
            outbox.state is OutboxState.DELIVERED
            and outbox.delivered_at is None
        ):
            anomalies.append("delivered_outbox_missing_delivered_at")
        if (
            outbox.state is OutboxState.DEAD
            and not str(outbox.last_error or "").strip()
        ):
            anomalies.append("dead_outbox_missing_last_error")

    if idempotency is not None:
        if idempotency.idempotency_key.tenant_id != tenant:
            anomalies.append("idempotency_tenant_id_mismatch")
        if (
            idempotency_key is not None
            and not idempotency.idempotency_key.same_scope(idempotency_key)
        ):
            anomalies.append("idempotency_scope_mismatch")
        if (
            latest is None
            and idempotency.state
            in {
                IdempotencyState.IN_PROGRESS,
                IdempotencyState.COMPLETED,
                IdempotencyState.FAILED,
            }
        ):
            anomalies.append("idempotency_exists_without_checkpoints")
        if (
            idempotency.state is IdempotencyState.COMPLETED
            and idempotency.completed_at is None
        ):
            anomalies.append("completed_idempotency_missing_completed_at")
        if (
            idempotency.state is IdempotencyState.IN_PROGRESS
            and not idempotency.has_live_lease(now=moment)
            and latest_stage in _LATE_LEASE_STAGES
        ):
            anomalies.append("late_run_with_expired_idempotency_lease")

    if latest is not None:
        if (
            latest_stage in rebuilder._required_outbox_stages
            and snapshot.resolved_outbox_id is None
        ):
            anomalies.append("late_stage_without_outbox_message_id_input")
        if (
            latest_stage in rebuilder._required_outbox_stages
            and not snapshot.outbox_ids
            and outbox is None
        ):
            anomalies.append("late_stage_without_any_outbox_reference")
        if (
            latest_stage in _LATE_IDEMPOTENCY_STAGES
            and idempotency_key is None
            and snapshot.canonical_idempotency_key is None
        ):
            anomalies.append("late_stage_without_any_idempotency_reference")

        if latest_stage == "completed":
            if (
                idempotency is not None
                and idempotency.state is not IdempotencyState.COMPLETED
            ):
                anomalies.append(
                    "completed_run_without_completed_idempotency"
                )
            if outbox is not None and outbox.state is not OutboxState.DELIVERED:
                anomalies.append("completed_run_without_delivered_outbox")
            if outbox is not None and outbox.is_claimable(now=moment):
                anomalies.append("completed_run_with_claimable_outbox")

        if latest_stage == "failed":
            if (
                idempotency is not None
                and idempotency.state is IdempotencyState.COMPLETED
            ):
                anomalies.append("failed_run_with_completed_idempotency")
            if outbox is not None and outbox.state is OutboxState.DELIVERED:
                anomalies.append("failed_run_with_delivered_outbox")

    if (
        outbox is not None
        and outbox.state is OutboxState.DELIVERED
        and latest_stage in {None, "request", "world_state", "decision"}
    ):
        anomalies.append("delivered_outbox_before_late_execution_stage")
    if (
        idempotency is not None
        and idempotency.state is IdempotencyState.FAILED
        and latest_stage == "completed"
    ):
        anomalies.append("idempotency_failed_but_run_completed")
    if (
        idempotency is not None
        and idempotency.state is IdempotencyState.COMPLETED
        and latest_stage == "failed"
    ):
        anomalies.append("idempotency_completed_but_run_failed")

    has_live_lease = bool(
        idempotency is not None
        and idempotency.state is IdempotencyState.IN_PROGRESS
        and idempotency.has_live_lease(now=moment)
    )
    outbox_claimable = bool(
        outbox is not None and outbox.is_claimable(now=moment)
    )
    if has_live_lease and outbox_claimable:
        anomalies.append("claimable_outbox_while_idempotency_lease_live")

    unique_anomalies = tuple(dict.fromkeys(anomalies))
    partial_history = graph_validation.inferred_entry_stage is not None
    base_resume = rebuilder._graph.safe_resume_point(latest_stage)
    resume_point = (
        base_resume
        if graph_validation.is_valid and not unique_anomalies
        else RecoveryResumePoint(
            action="quarantine",
            stage=None,
            reason="invalid_rebuilt_run_facts",
        )
    )
    derived_flags = {
        "graph_is_valid": graph_validation.is_valid,
        "graph_can_resume": graph_validation.can_resume,
        "partial_history_detected": partial_history,
        "inferred_entry_stage": graph_validation.inferred_entry_stage,
        "skipped_forward_stages": tuple(
            graph_validation.skipped_forward_stages
        ),
        "resume_action": resume_point.action,
        "resume_stage": resume_point.stage,
        "resume_reason": resume_point.reason,
        "snapshot_stable": snapshot_stable,
        "resolved_outbox_message_id": snapshot.resolved_outbox_id,
        "has_live_idempotency_lease": has_live_lease,
        "idempotency_terminal": bool(
            idempotency is not None
            and idempotency.state
            in {IdempotencyState.COMPLETED, IdempotencyState.FAILED}
        ),
        "outbox_claimable": outbox_claimable,
        "outbox_delivered": bool(
            outbox is not None and outbox.state is OutboxState.DELIVERED
        ),
        "outbox_dead": bool(
            outbox is not None and outbox.state is OutboxState.DEAD
        ),
        "run_terminal": bool(latest_stage in {"completed", "failed"}),
        "cross_store_consistent": not unique_anomalies,
        "claimable_outbox_while_idempotency_lease_live": bool(
            has_live_lease and outbox_claimable
        ),
    }
    return RebuiltRunFacts(
        tenant_id=tenant,
        run_id=run,
        latest_stage=latest_stage,
        latest_checkpoint=latest,
        checkpoints=checkpoints,
        idempotency_record=idempotency,
        outbox_message=outbox,
        graph_validation=graph_validation,
        reconciliation=reconciliation,
        resume_point=resume_point,
        anomalies=unique_anomalies,
        derived_flags=derived_flags,
        canonical_outbox_message_id=snapshot.canonical_outbox_id,
        canonical_idempotency_key=snapshot.canonical_idempotency_key,
        partial_history_detected=partial_history,
        observed_at=moment,
    )



__all__ = ["rebuild_facts"]
