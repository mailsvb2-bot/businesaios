from __future__ import annotations

from datetime import timedelta
from types import MappingProxyType

import pytest

from reliability.idempotency_contract import IdempotencyState
from reliability.outbox_store import OutboxState
from reliability.recovery_run_rebuilder import RebuiltRunFacts, RecoveryRunRebuilder
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


def rebuilder(checkpoints=(), idem=None, outbox=None, **kwargs):
    return RecoveryRunRebuilder(
        checkpoint_store=SequenceCheckpointStore(checkpoints, checkpoints),
        idempotency_store=SequenceIdempotencyStore(idem, idem),
        outbox_store=SequenceOutboxStore(outbox, outbox),
        **kwargs,
    )


def test_strict_inputs_fail_before_store_io() -> None:
    cp = SequenceCheckpointStore(())
    idem = SequenceIdempotencyStore(None)
    outbox = SequenceOutboxStore(None)
    subject = RecoveryRunRebuilder(
        checkpoint_store=cp,
        idempotency_store=idem,
        outbox_store=outbox,
    )

    with pytest.raises(ValueError, match="tenant_id"):
        subject.rebuild(tenant_id="default", run_id=RUN)
    with pytest.raises(ValueError, match="run_id"):
        subject.rebuild(tenant_id=TENANT, run_id=" ")
    with pytest.raises(ValueError, match="outbox_message_id"):
        subject.rebuild(
            tenant_id=TENANT,
            run_id=RUN,
            outbox_message_id=" ",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        subject.rebuild(
            tenant_id=TENANT,
            run_id=RUN,
            observed_at=NOW.replace(tzinfo=None),
        )
    wrong_key = KEY.__class__(
        tenant_id="tenant-b",
        namespace=KEY.namespace,
        operation=KEY.operation,
        key=KEY.key,
        scope_hash=KEY.scope_hash,
    )
    with pytest.raises(ValueError, match="must match"):
        subject.rebuild(
            tenant_id=TENANT,
            run_id=RUN,
            idempotency_key=wrong_key,
        )
    assert cp.calls == []
    assert idem.calls == []
    assert outbox.calls == []

    with pytest.raises(ValueError, match="unknown recovery stage"):
        RecoveryRunRebuilder(
            checkpoint_store=cp,
            idempotency_store=idem,
            outbox_store=outbox,
            required_outbox_stages=("bogus",),
        )


def test_clean_execution_auto_resolves_checkpoint_outbox() -> None:
    checkpoints = path_to("execution")
    idem = idempotency_record()
    outbox = outbox_message(available_at=NOW + timedelta(minutes=1))
    cp_store = SequenceCheckpointStore(checkpoints, checkpoints)
    idem_store = SequenceIdempotencyStore(idem, idem)
    outbox_store = SequenceOutboxStore(outbox, outbox)
    facts = RecoveryRunRebuilder(
        checkpoint_store=cp_store,
        idempotency_store=idem_store,
        outbox_store=outbox_store,
        required_outbox_stages=("execution", "execution"),
    ).rebuild(
        tenant_id=f" {TENANT} ",
        run_id=f" {RUN} ",
        idempotency_key=KEY,
        observed_at=NOW,
    )

    assert facts.tenant_id == TENANT
    assert facts.run_id == RUN
    assert facts.latest_stage == "execution"
    assert facts.checkpoint_count == 5
    assert facts.is_clean
    assert not facts.is_terminal
    assert facts.idempotency_state == "in_progress"
    assert facts.outbox_state == "pending"
    assert facts.has_live_idempotency_lease
    assert not facts.idempotency_is_terminal
    assert not facts.outbox_is_claimable
    assert not facts.outbox_is_delivered
    assert not facts.outbox_is_dead
    assert facts.canonical_outbox_message_id == OUTBOX_ID
    assert facts.canonical_idempotency_key == RUN
    assert facts.outbox_message is outbox
    assert facts.resume_point.action == "resume_execution"
    assert facts.derived_flags["snapshot_stable"] is True
    assert facts.derived_flags["resolved_outbox_message_id"] == OUTBOX_ID
    assert facts.derived_flags["cross_store_consistent"] is True
    assert isinstance(facts.derived_flags, MappingProxyType)
    with pytest.raises(TypeError):
        facts.derived_flags["mutate"] = True
    assert cp_store.calls == [(TENANT, RUN), (TENANT, RUN)]
    assert idem_store.calls == [KEY, KEY]
    assert outbox_store.calls == [(TENANT, OUTBOX_ID)] * 2


def test_clean_empty_partial_completed_and_failed_paths() -> None:
    empty = rebuilder().rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        observed_at=NOW,
    )
    assert empty.latest_stage is None
    assert empty.resume_point.action == "restart_from_scratch"
    assert empty.idempotency_state is None
    assert empty.outbox_state is None
    assert not empty.has_live_idempotency_lease
    assert not empty.idempotency_is_terminal
    assert not empty.outbox_is_claimable

    partial_checkpoints = (
        checkpoint("execution", 4),
        checkpoint("verification", 5),
    )
    partial = rebuilder(
        partial_checkpoints,
        idempotency_record(),
        outbox_message(),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert partial.partial_history_detected
    assert partial.derived_flags["inferred_entry_stage"] == "execution"
    assert partial.resume_point.action == "resume_execution"

    completed = rebuilder(
        path_to("completed"),
        idempotency_record(IdempotencyState.COMPLETED),
        outbox_message(OutboxState.DELIVERED),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert completed.is_terminal
    assert completed.idempotency_is_terminal
    assert completed.outbox_is_delivered
    assert completed.resume_point.action == "terminal_noop"
    assert completed.derived_flags["run_terminal"] is True

    failed = rebuilder(
        path_to("failed"),
        idempotency_record(IdempotencyState.FAILED),
        outbox_message(OutboxState.DEAD),
    ).rebuild(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
        observed_at=NOW,
    )
    assert failed.is_terminal
    assert failed.idempotency_is_terminal
    assert failed.outbox_is_dead
    assert failed.resume_point.action == "terminal_noop"


def test_rebuilt_facts_default_factories_and_validation() -> None:
    facts = RebuiltRunFacts(
        tenant_id=TENANT,
        run_id=RUN,
        latest_stage=None,
        latest_checkpoint=None,
        anomalies=("x", "x"),
        derived_flags={"a": 1},
        observed_at=NOW,
    )
    assert facts.anomalies == ("x",)
    assert not facts.is_clean
    assert facts.graph_validation.is_valid
    assert facts.reconciliation.checkpoint_count == 0
    assert facts.resume_point.stage == "request"

    with pytest.raises(ValueError, match="tenant_id"):
        RebuiltRunFacts(
            tenant_id="default",
            run_id=RUN,
            latest_stage=None,
            latest_checkpoint=None,
        )
    with pytest.raises(ValueError, match="run_id"):
        RebuiltRunFacts(
            tenant_id=TENANT,
            run_id="",
            latest_stage=None,
            latest_checkpoint=None,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        RebuiltRunFacts(
            tenant_id=TENANT,
            run_id=RUN,
            latest_stage=None,
            latest_checkpoint=None,
            observed_at=NOW.replace(tzinfo=None),
        )
