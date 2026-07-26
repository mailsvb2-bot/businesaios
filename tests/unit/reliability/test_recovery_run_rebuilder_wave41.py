from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from reliability.execution_checkpoint_store import ExecutionCheckpoint
from reliability.idempotency_contract import (
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyState,
)
from reliability.outbox_store import OutboxMessage, OutboxState
from reliability.recovery_run_rebuilder import RecoveryRunRebuilder

UTC = timezone.utc
NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


class Checkpoints:
    def __init__(self, items=()):
        self.items = tuple(items)
        self.calls = 0

    def list_run(self, *, tenant_id, run_id):
        self.calls += 1
        return self.items


class Idempotency:
    def __init__(self, record=None):
        self.record = record
        self.calls = 0

    def get(self, *, key):
        self.calls += 1
        return self.record


class Outbox:
    def __init__(self, message=None):
        self.message = message
        self.calls = 0

    def get(self, *, tenant_id, message_id):
        self.calls += 1
        return self.message


def checkpoint(*, tenant="tenant-a", run="run-1", stage="execution"):
    return ExecutionCheckpoint(
        tenant_id=tenant,
        run_id=run,
        sequence_no=1,
        stage=stage,
        checkpoint_id="cp-1",
        created_at=NOW,
        idempotency_key="idem-1",
        outbox_message_id="msg-1",
    )


def idem_record(*, expires_at):
    return IdempotencyRecord(
        idempotency_key=IdempotencyKey(
            tenant_id="tenant-a",
            namespace="runtime",
            operation="execute",
            key="idem-1",
        ),
        state=IdempotencyState.IN_PROGRESS,
        first_seen_at=NOW - timedelta(minutes=1),
        updated_at=NOW - timedelta(minutes=1),
        lease_expires_at=expires_at,
        owner_id="worker-a",
        attempt_count=1,
    )


def outbox_message(*, available_at):
    return OutboxMessage(
        tenant_id="tenant-a",
        message_id="msg-1",
        topic="effects",
        dedupe_key="dedupe-1",
        payload={"ok": True},
        state=OutboxState.PENDING,
        created_at=NOW - timedelta(minutes=1),
        updated_at=NOW - timedelta(minutes=1),
        available_at=available_at,
        run_id="run-1",
    )


def make_rebuilder(checkpoints, idem, outbox):
    return RecoveryRunRebuilder(
        checkpoint_store=checkpoints,
        idempotency_store=idem,
        outbox_store=outbox,
    )


def test_rebuild_reads_each_store_once_and_reconciles_same_snapshot():
    cps = Checkpoints([checkpoint()])
    idem = Idempotency(idem_record(expires_at=NOW + timedelta(seconds=1)))
    outbox = Outbox(outbox_message(available_at=NOW))

    facts = make_rebuilder(cps, idem, outbox).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=idem.record.idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )

    assert (cps.calls, idem.calls, outbox.calls) == (1, 1, 1)
    assert facts.reconciliation.checkpoint_count == facts.checkpoint_count == 1
    assert facts.reconciliation.idempotency_state == facts.idempotency_state
    assert facts.reconciliation.outbox_state == facts.outbox_state


def test_rebuild_uses_one_observation_time_for_all_temporal_flags():
    cps = Checkpoints([checkpoint()])
    idem = Idempotency(idem_record(expires_at=NOW + timedelta(microseconds=1)))
    outbox = Outbox(outbox_message(available_at=NOW + timedelta(microseconds=1)))

    facts = make_rebuilder(cps, idem, outbox).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=idem.record.idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )

    assert facts.observed_at == NOW
    assert facts.has_live_idempotency_lease is True
    assert facts.outbox_is_claimable is False
    assert facts.derived_flags["has_live_idempotency_lease"] is True
    assert facts.derived_flags["outbox_claimable"] is False


def test_rebuild_validates_scope_before_store_io():
    cps, idem, outbox = Checkpoints(), Idempotency(), Outbox()
    rebuilder = make_rebuilder(cps, idem, outbox)

    with pytest.raises(ValueError, match="run_id is required"):
        rebuilder.rebuild(tenant_id="tenant-a", run_id=" ")
    with pytest.raises(ValueError, match="timezone-aware"):
        rebuilder.rebuild(
            tenant_id="tenant-a", run_id="run-1", now=datetime(2026, 1, 1)
        )
    with pytest.raises(ValueError, match="tenant does not match"):
        rebuilder.rebuild(
            tenant_id="tenant-a",
            run_id="run-1",
            idempotency_key=IdempotencyKey(
                tenant_id="tenant-b",
                namespace="runtime",
                operation="execute",
                key="idem-1",
            ),
        )

    assert (cps.calls, idem.calls, outbox.calls) == (0, 0, 0)


def test_rebuild_quarantines_store_scope_leak_and_freezes_flags():
    cps = Checkpoints([checkpoint(tenant="tenant-b", run="run-other")])
    facts = make_rebuilder(cps, Idempotency(), Outbox()).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        now=NOW,
    )

    assert "checkpoint_tenant_id_mismatch" in facts.anomalies
    assert "checkpoint_run_id_mismatch" in facts.anomalies
    assert facts.derived_flags["cross_store_consistent"] is False
    with pytest.raises(TypeError):
        facts.derived_flags["cross_store_consistent"] = True


def completed_idem(*, state=IdempotencyState.COMPLETED, completed_at=NOW):
    return IdempotencyRecord(
        idempotency_key=IdempotencyKey(
            tenant_id="tenant-a", namespace="runtime", operation="execute", key="idem-1"
        ),
        state=state,
        first_seen_at=NOW - timedelta(minutes=2),
        updated_at=NOW - timedelta(minutes=1),
        completed_at=completed_at,
        owner_id="worker-a",
        attempt_count=1,
    )


def state_outbox(
    *, state, tenant="tenant-a", run="run-1", delivered_at=NOW, last_error="boom"
):
    return OutboxMessage(
        tenant_id=tenant,
        message_id="msg-1",
        topic="effects",
        dedupe_key="dedupe-1",
        payload={"ok": True},
        state=state,
        created_at=NOW - timedelta(minutes=2),
        updated_at=NOW - timedelta(minutes=1),
        available_at=NOW - timedelta(minutes=1),
        run_id=run,
        delivered_at=delivered_at if state is OutboxState.DELIVERED else None,
        last_error=last_error if state is OutboxState.DEAD else None,
    )


def test_fact_properties_cover_empty_and_terminal_states():
    empty = make_rebuilder(Checkpoints(), Idempotency(), Outbox()).rebuild(
        tenant_id="tenant-a", run_id="run-1", now=NOW
    )
    assert empty.checkpoint_count == 0
    assert empty.is_terminal is False
    assert empty.is_clean is True
    assert empty.idempotency_state is None
    assert empty.outbox_state is None
    assert empty.has_live_idempotency_lease is False
    assert empty.idempotency_is_terminal is False
    assert empty.outbox_is_claimable is False
    assert empty.outbox_is_delivered is False
    assert empty.outbox_is_dead is False

    failed = make_rebuilder(
        Checkpoints([checkpoint(stage="failed")]),
        Idempotency(completed_idem(state=IdempotencyState.FAILED, completed_at=None)),
        Outbox(state_outbox(state=OutboxState.DEAD)),
    ).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=completed_idem(
            state=IdempotencyState.FAILED, completed_at=None
        ).idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )
    assert failed.is_terminal is True
    assert failed.idempotency_is_terminal is True
    assert failed.outbox_is_dead is True


def test_multiple_checkpoint_references_and_requested_mismatches_are_reported():
    first = checkpoint(stage="execution")
    second = ExecutionCheckpoint(
        tenant_id="tenant-a",
        run_id="run-1",
        sequence_no=2,
        stage="verification",
        checkpoint_id="cp-2",
        created_at=NOW,
        trace_id="trace-2",
        decision_id="decision-2",
        idempotency_key="idem-2",
        outbox_message_id="msg-2",
    )
    first = ExecutionCheckpoint(
        **{**first.__dict__, "trace_id": "trace-1", "decision_id": "decision-1"}
    )
    facts = make_rebuilder(Checkpoints([first, second]), Idempotency(), Outbox()).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=IdempotencyKey(
            tenant_id="tenant-a",
            namespace="runtime",
            operation="execute",
            key="requested",
        ),
        outbox_message_id="requested-msg",
        now=NOW,
    )
    for anomaly in (
        "multiple_outbox_message_ids_in_single_run",
        "multiple_idempotency_keys_in_single_run",
        "multiple_trace_ids_in_single_run",
        "multiple_decision_ids_in_single_run",
        "latest_checkpoint_outbox_message_id_mismatch",
        "latest_checkpoint_idempotency_key_mismatch",
        "outbox_message_id_provided_but_missing",
        "late_run_without_idempotency_record",
    ):
        assert anomaly in facts.anomalies


def test_outbox_integrity_anomalies_cover_missing_and_invalid_terminal_metadata():
    delivered = state_outbox(
        state=OutboxState.DELIVERED, tenant="tenant-b", run="other", delivered_at=None
    )
    facts = make_rebuilder(Checkpoints(), Idempotency(), Outbox(delivered)).rebuild(
        tenant_id="tenant-a", run_id="run-1", outbox_message_id="msg-1", now=NOW
    )
    for anomaly in (
        "outbox_exists_without_checkpoints",
        "outbox_run_id_mismatch",
        "outbox_tenant_id_mismatch",
        "delivered_outbox_missing_delivered_at",
        "delivered_outbox_before_late_execution_stage",
    ):
        assert anomaly in facts.anomalies
    assert facts.outbox_is_delivered is True

    dead = state_outbox(state=OutboxState.DEAD, last_error="")
    dead_facts = make_rebuilder(Checkpoints(), Idempotency(), Outbox(dead)).rebuild(
        tenant_id="tenant-a", run_id="run-1", outbox_message_id="msg-1", now=NOW
    )
    assert "dead_outbox_missing_last_error" in dead_facts.anomalies


def test_idempotency_and_terminal_cross_store_anomalies():
    expired = idem_record(expires_at=NOW - timedelta(seconds=1))
    late = make_rebuilder(
        Checkpoints([checkpoint(stage="execution")]), Idempotency(expired), Outbox()
    ).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=expired.idempotency_key,
        now=NOW,
    )
    assert "late_run_with_expired_idempotency_lease" in late.anomalies
    assert "late_stage_without_outbox_message_id_input" not in late.anomalies

    completed_bad = completed_idem(completed_at=None)
    no_cp = make_rebuilder(Checkpoints(), Idempotency(completed_bad), Outbox()).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=completed_bad.idempotency_key,
        now=NOW,
    )
    assert "idempotency_exists_without_checkpoints" in no_cp.anomalies
    assert "completed_idempotency_missing_completed_at" in no_cp.anomalies

    pending = state_outbox(state=OutboxState.PENDING)
    completed = make_rebuilder(
        Checkpoints([checkpoint(stage="completed")]),
        Idempotency(expired),
        Outbox(pending),
    ).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=expired.idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )
    for anomaly in (
        "completed_run_without_completed_idempotency",
        "completed_run_without_delivered_outbox",
        "completed_run_with_claimable_outbox",
    ):
        assert anomaly in completed.anomalies


def test_failed_and_completed_cross_store_conflicts():
    delivered = state_outbox(state=OutboxState.DELIVERED)
    completed = completed_idem()
    failed = make_rebuilder(
        Checkpoints([checkpoint(stage="failed")]),
        Idempotency(completed),
        Outbox(delivered),
    ).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=completed.idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )
    for anomaly in (
        "failed_run_with_completed_idempotency",
        "failed_run_with_delivered_outbox",
        "idempotency_completed_but_run_failed",
    ):
        assert anomaly in failed.anomalies


def test_property_fallbacks_without_derived_snapshot_flags():
    from reliability.recovery_run_rebuilder import RebuiltRunFacts

    live = idem_record(expires_at=NOW + timedelta(seconds=1))
    pending = outbox_message(available_at=NOW)
    facts = RebuiltRunFacts(
        tenant_id="tenant-a",
        run_id="run-1",
        latest_stage="execution",
        latest_checkpoint=None,
        idempotency_record=live,
        outbox_message=pending,
        observed_at=NOW,
    )
    assert facts.has_live_idempotency_lease is True
    assert facts.outbox_is_claimable is True


def test_single_canonical_references_can_mismatch_requested_values():
    cp = checkpoint()
    facts = make_rebuilder(Checkpoints([cp]), Idempotency(), Outbox()).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=IdempotencyKey(
            tenant_id="tenant-a", namespace="runtime", operation="execute", key="other"
        ),
        outbox_message_id="other-msg",
        now=NOW,
    )
    assert "requested_outbox_message_id_mismatch" in facts.anomalies
    assert "requested_idempotency_key_mismatch" in facts.anomalies


def test_late_stage_without_any_references_is_quarantined():
    bare = ExecutionCheckpoint(
        tenant_id="tenant-a",
        run_id="run-1",
        sequence_no=1,
        stage="execution",
        checkpoint_id="cp-bare",
        created_at=NOW,
    )
    facts = make_rebuilder(Checkpoints([bare]), Idempotency(), Outbox()).rebuild(
        tenant_id="tenant-a", run_id="run-1", now=NOW
    )
    for anomaly in (
        "late_stage_without_outbox_message_id_input",
        "late_stage_without_any_outbox_reference",
        "late_stage_without_any_idempotency_reference",
    ):
        assert anomaly in facts.anomalies


def test_store_returned_wrong_idempotency_tenant_is_reported():
    wrong = IdempotencyRecord(
        idempotency_key=IdempotencyKey(
            tenant_id="tenant-b", namespace="runtime", operation="execute", key="idem-1"
        ),
        state=IdempotencyState.STARTED,
        first_seen_at=NOW,
        updated_at=NOW,
    )
    requested = IdempotencyKey(
        tenant_id="tenant-a", namespace="runtime", operation="execute", key="idem-1"
    )
    facts = make_rebuilder(
        Checkpoints([checkpoint()]), Idempotency(wrong), Outbox()
    ).rebuild(
        tenant_id="tenant-a", run_id="run-1", idempotency_key=requested, now=NOW
    )
    assert "idempotency_tenant_id_mismatch" in facts.anomalies


def test_completed_run_with_failed_idempotency_and_clean_outbox_conflicts():
    failed_idem = completed_idem(state=IdempotencyState.FAILED, completed_at=None)
    delivered = state_outbox(state=OutboxState.DELIVERED)
    facts = make_rebuilder(
        Checkpoints([checkpoint(stage="completed")]),
        Idempotency(failed_idem),
        Outbox(delivered),
    ).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=failed_idem.idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )
    assert "completed_run_without_completed_idempotency" in facts.anomalies
    assert "idempotency_failed_but_run_completed" in facts.anomalies


def test_execution_reconciliation_public_and_corrupt_sequences():
    from reliability.execution_reconciliation import ExecutionReconciliation

    first = checkpoint(stage="execution")
    duplicate = ExecutionCheckpoint(
        **{**first.__dict__, "sequence_no": 2, "stage": "verification"}
    )
    cps = Checkpoints([first, duplicate])
    idem = Idempotency(completed_idem())
    outbox = Outbox(state_outbox(state=OutboxState.DELIVERED))
    report = ExecutionReconciliation(
        checkpoint_store=cps,
        idempotency_store=idem,
        outbox_store=outbox,
    ).reconcile(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=idem.record.idempotency_key,
        outbox_message_id="msg-1",
    )
    assert "duplicate_checkpoint_id" in report.anomalies
    assert report.is_clean is False
    assert (cps.calls, idem.calls, outbox.calls) == (1, 1, 1)

    non_monotonic = ExecutionCheckpoint(
        **{**first.__dict__, "checkpoint_id": "cp-2", "sequence_no": 0}
    )
    report = ExecutionReconciliation(
        checkpoint_store=Checkpoints(),
        idempotency_store=Idempotency(),
        outbox_store=Outbox(),
    ).reconcile_snapshot(
        run_id="run-1",
        checkpoints=(first, non_monotonic),
        idempotency_record=None,
        outbox_message=None,
    )
    assert "non_monotonic_sequence" in report.anomalies


def test_remaining_clean_branch_edges():
    from reliability.execution_reconciliation import ExecutionReconciliation

    first = ExecutionCheckpoint(
        tenant_id="tenant-a",
        run_id="run-1",
        sequence_no=1,
        stage="execution",
        checkpoint_id="same",
        created_at=NOW,
        decision_id="d",
        action_id="a",
    )
    same_retry = ExecutionCheckpoint(
        **{**first.__dict__, "sequence_no": 2}
    )
    clean_retry = ExecutionReconciliation(
        checkpoint_store=Checkpoints(),
        idempotency_store=Idempotency(),
        outbox_store=Outbox(),
    ).reconcile_snapshot(
        run_id="run-1",
        checkpoints=(first, same_retry),
        idempotency_record=None,
        outbox_message=None,
    )
    assert "duplicate_checkpoint_id" not in clean_retry.anomalies

    completed = completed_idem()
    pending = state_outbox(state=OutboxState.PENDING)
    completed_report = ExecutionReconciliation(
        checkpoint_store=Checkpoints(),
        idempotency_store=Idempotency(),
        outbox_store=Outbox(),
    ).reconcile_snapshot(
        run_id="run-1",
        checkpoints=(checkpoint(stage="completed"),),
        idempotency_record=completed,
        outbox_message=pending,
    )
    assert (
        "completed_checkpoint_but_idempotency_not_completed"
        not in completed_report.anomalies
    )
    assert "completed_checkpoint_but_outbox_not_delivered" in completed_report.anomalies

    early_delivery = ExecutionReconciliation(
        checkpoint_store=Checkpoints(),
        idempotency_store=Idempotency(),
        outbox_store=Outbox(),
    ).reconcile_snapshot(
        run_id="run-1",
        checkpoints=(checkpoint(stage="request"),),
        idempotency_record=None,
        outbox_message=state_outbox(state=OutboxState.DELIVERED),
    )
    assert "outbox_delivered_before_late_execution_stage" in early_delivery.anomalies


def test_missing_idempotency_early_stage_and_completed_clean_idempotency_edges():
    requested = IdempotencyKey(
        tenant_id="tenant-a", namespace="runtime", operation="execute", key="idem-1"
    )
    early = make_rebuilder(
        Checkpoints([checkpoint(stage="request")]), Idempotency(), Outbox()
    ).rebuild(
        tenant_id="tenant-a", run_id="run-1", idempotency_key=requested, now=NOW
    )
    assert "late_run_without_idempotency_record" not in early.anomalies

    completed = completed_idem()
    facts = make_rebuilder(
        Checkpoints([checkpoint(stage="completed")]),
        Idempotency(completed),
        Outbox(state_outbox(state=OutboxState.DELIVERED)),
    ).rebuild(
        tenant_id="tenant-a",
        run_id="run-1",
        idempotency_key=completed.idempotency_key,
        outbox_message_id="msg-1",
        now=NOW,
    )
    assert "completed_run_without_completed_idempotency" not in facts.anomalies
