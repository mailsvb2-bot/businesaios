from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from reliability.idempotency_contract import IdempotencyKey, IdempotencyState
from reliability.outbox_store import OutboxState
from reliability.recovery_run_rebuilder import RecoveryRunRebuilder
from tests.unit.reliability.recovery_run_wave41_support import (
    KEY,
    NOW,
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


def build(cp_store, idem_store=None, outbox_store=None, **kwargs):
    return RecoveryRunRebuilder(
        checkpoint_store=cp_store,
        idempotency_store=idem_store or SequenceIdempotencyStore(None),
        outbox_store=outbox_store or SequenceOutboxStore(None),
        **kwargs,
    )


def test_unstable_and_invalid_checkpoint_snapshot_is_quarantined() -> None:
    first = (checkpoint("request", 0),)
    second = (
        checkpoint(
            "bogus",
            0,
            tenant_id="tenant-b",
            run_id="run-x",
            outbox_message_id="message-a",
            idempotency_key="key-a",
            trace_id="trace-a",
            decision_id="decision-a",
        ),
        checkpoint(
            "request",
            1,
            outbox_message_id="message-b",
            idempotency_key="key-b",
            trace_id="trace-b",
            decision_id="decision-b",
        ),
    )
    facts = build(SequenceCheckpointStore(first, second)).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        observed_at=NOW,
    )

    expected = {
        "checkpoint_validation_error",
        "unstable_recovery_snapshot",
        "checkpoint_tenant_id_mismatch",
        "checkpoint_run_id_mismatch",
        "multiple_outbox_message_ids_in_single_run",
        "multiple_idempotency_keys_in_single_run",
        "multiple_trace_ids_in_single_run",
        "multiple_decision_ids_in_single_run",
    }
    assert expected.issubset(set(facts.anomalies))
    assert facts.resume_point.action == "quarantine"
    assert facts.derived_flags["snapshot_stable"] is False
    assert facts.derived_flags["cross_store_consistent"] is False


def test_explicit_reference_drift_and_missing_records_are_detected() -> None:
    checkpoints = (
        checkpoint(
            "execution",
            4,
            outbox_message_id="checkpoint-message",
            idempotency_key="checkpoint-key",
        ),
    )
    facts = build(
        SequenceCheckpointStore(checkpoints, checkpoints),
        SequenceIdempotencyStore(None, None),
        SequenceOutboxStore(None, None),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        outbox_message_id="requested-message",
        observed_at=NOW,
    )

    assert {
        "requested_outbox_message_id_mismatch",
        "latest_checkpoint_outbox_message_id_mismatch",
        "requested_idempotency_key_mismatch",
        "latest_checkpoint_idempotency_key_mismatch",
        "canonical_outbox_message_id_missing",
        "late_run_without_idempotency_record",
    }.issubset(set(facts.anomalies))
    assert facts.resume_point.action == "quarantine"


def test_missing_explicit_and_checkpoint_references_fail_closed() -> None:
    no_refs = (
        checkpoint(
            "execution",
            4,
            outbox_message_id=None,
            idempotency_key=None,
            trace_id=None,
            decision_id=None,
        ),
    )
    explicit_missing = build(
        SequenceCheckpointStore(no_refs, no_refs),
        outbox_store=SequenceOutboxStore(None, None),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        outbox_message_id="missing-message",
        observed_at=NOW,
    )
    assert "outbox_message_id_provided_but_missing" in explicit_missing.anomalies
    assert "late_stage_without_any_outbox_reference" in explicit_missing.anomalies
    assert "late_stage_without_any_idempotency_reference" in (
        explicit_missing.anomalies
    )

    no_explicit = build(
        SequenceCheckpointStore(no_refs, no_refs),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        observed_at=NOW,
    )
    assert "late_stage_without_outbox_message_id_input" in no_explicit.anomalies
    assert "late_stage_without_any_outbox_reference" in no_explicit.anomalies

    checkpoint_key_only = (
        checkpoint(
            "execution",
            4,
            outbox_message_id=OUTBOX_ID,
            idempotency_key=RUN,
        ),
    )
    unresolved = build(
        SequenceCheckpointStore(checkpoint_key_only, checkpoint_key_only),
        outbox_store=SequenceOutboxStore(
            outbox_message(),
            outbox_message(),
        ),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        observed_at=NOW,
    )
    assert "idempotency_record_unresolved_from_checkpoint_reference" in (
        unresolved.anomalies
    )


def test_outbox_identity_state_and_orphan_anomalies() -> None:
    malformed_delivered = replace(
        outbox_message(OutboxState.DELIVERED),
        tenant_id="tenant-b",
        message_id="wrong-message",
        run_id="run-x",
        delivered_at=None,
    )
    facts = build(
        SequenceCheckpointStore((), ()),
        outbox_store=SequenceOutboxStore(
            malformed_delivered,
            malformed_delivered,
        ),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        outbox_message_id=OUTBOX_ID,
        observed_at=NOW,
    )
    assert {
        "outbox_exists_without_checkpoints",
        "outbox_message_id_mismatch",
        "outbox_run_id_mismatch",
        "outbox_tenant_id_mismatch",
        "delivered_outbox_missing_delivered_at",
        "delivered_outbox_before_late_execution_stage",
    }.issubset(set(facts.anomalies))

    malformed_dead = replace(
        outbox_message(OutboxState.DEAD),
        last_error="",
    )
    dead = build(
        SequenceCheckpointStore((), ()),
        outbox_store=SequenceOutboxStore(malformed_dead, malformed_dead),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        outbox_message_id=OUTBOX_ID,
        observed_at=NOW,
    )
    assert "dead_outbox_missing_last_error" in dead.anomalies


def test_idempotency_scope_tenant_terminal_and_expiry_anomalies() -> None:
    returned_key = IdempotencyKey(
        tenant_id="tenant-b",
        namespace=KEY.namespace,
        operation=KEY.operation,
        key=KEY.key,
        scope_hash="other-scope",
    )
    malformed_completed = idempotency_record(
        IdempotencyState.COMPLETED,
        key=returned_key,
    )
    malformed_completed = replace(malformed_completed, completed_at=None)
    orphan = build(
        SequenceCheckpointStore((), ()),
        SequenceIdempotencyStore(
            malformed_completed,
            malformed_completed,
        ),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert {
        "idempotency_tenant_id_mismatch",
        "idempotency_scope_mismatch",
        "idempotency_exists_without_checkpoints",
        "completed_idempotency_missing_completed_at",
    }.issubset(set(orphan.anomalies))

    expired = idempotency_record(
        IdempotencyState.IN_PROGRESS,
        lease_expires_at=NOW - timedelta(seconds=1),
    )
    late = build(
        SequenceCheckpointStore(path_to("execution"), path_to("execution")),
        SequenceIdempotencyStore(expired, expired),
        SequenceOutboxStore(outbox_message(), outbox_message()),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert "late_run_with_expired_idempotency_lease" in late.anomalies


def test_completed_failed_and_live_lease_delivery_conflicts() -> None:
    live = idempotency_record(IdempotencyState.IN_PROGRESS)
    claimable = outbox_message(
        OutboxState.PENDING,
        available_at=NOW,
    )
    completed = build(
        SequenceCheckpointStore(path_to("completed"), path_to("completed")),
        SequenceIdempotencyStore(live, live),
        SequenceOutboxStore(claimable, claimable),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert {
        "completed_run_without_completed_idempotency",
        "completed_run_without_delivered_outbox",
        "completed_run_with_claimable_outbox",
        "claimable_outbox_while_idempotency_lease_live",
    }.issubset(set(completed.anomalies))
    assert completed.derived_flags[
        "claimable_outbox_while_idempotency_lease_live"
    ] is True

    completed_idem = idempotency_record(IdempotencyState.COMPLETED)
    delivered = outbox_message(OutboxState.DELIVERED)
    failed = build(
        SequenceCheckpointStore(path_to("failed"), path_to("failed")),
        SequenceIdempotencyStore(completed_idem, completed_idem),
        SequenceOutboxStore(delivered, delivered),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert {
        "failed_run_with_completed_idempotency",
        "failed_run_with_delivered_outbox",
        "idempotency_completed_but_run_failed",
    }.issubset(set(failed.anomalies))

    failed_idem = idempotency_record(IdempotencyState.FAILED)
    completed_failed = build(
        SequenceCheckpointStore(path_to("completed"), path_to("completed")),
        SequenceIdempotencyStore(failed_idem, failed_idem),
        SequenceOutboxStore(delivered, delivered),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert "idempotency_failed_but_run_completed" in completed_failed.anomalies
