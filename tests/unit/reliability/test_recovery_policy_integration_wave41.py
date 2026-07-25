from __future__ import annotations

from datetime import datetime, timedelta, timezone

from reliability.execution_checkpoint_store import InMemoryExecutionCheckpointStore
from reliability.idempotency_contract import IdempotencyState
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore, OutboxState
from reliability.recovery_orchestrator import RecoveryOrchestrator
from reliability.recovery_policy_engine import (
    RecoveryPolicyConfig,
    RecoveryPolicyEngine,
)
from tests.unit.reliability.recovery_run_wave41_support import (
    KEY,
    OUTBOX_ID,
    RUN,
    TENANT,
    SequenceCheckpointStore,
    SequenceIdempotencyStore,
    SequenceOutboxStore,
    idempotency_record,
    outbox_message,
    path_to,
)


def stores(*, claimable: bool):
    now = datetime.now(timezone.utc)
    checkpoints = InMemoryExecutionCheckpointStore()
    for item in path_to("execution"):
        checkpoints.append(item)

    idempotency = InMemoryIdempotencyStore()
    idempotency.reserve(
        key=KEY,
        owner_id="worker-1",
        lease_ttl_seconds=3600,
        now=now,
    )

    outbox = InMemoryOutboxStore()
    message = outbox_message(
        available_at=(
            now - timedelta(seconds=1)
            if claimable
            else now + timedelta(hours=1)
        )
    )
    outbox.enqueue(message)
    return checkpoints, idempotency, outbox


def test_policy_and_orchestrator_use_auto_resolved_snapshot() -> None:
    checkpoints, idempotency, outbox = stores(claimable=False)
    engine = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    )
    decision = engine.resolve(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
    )
    assert decision.action == "wait"
    assert decision.reason == "live_idempotency_lease"
    assert decision.anomalies == ()
    assert decision.rebuilt_facts is not None
    assert decision.rebuilt_facts.outbox_message is not None
    assert decision.rebuilt_facts.outbox_message.message_id == OUTBOX_ID

    plan = RecoveryOrchestrator(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    ).plan(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
    )
    assert plan.recovery_action == "wait"
    assert plan.reconciliation.is_clean
    assert plan.reconciliation.outbox_state == "pending"
    assert plan.anomalies == ()


def test_live_lease_claimable_outbox_is_hard_quarantined() -> None:
    checkpoints, idempotency, outbox = stores(claimable=True)
    config = RecoveryPolicyConfig(
        quarantine_on_any_anomaly=False,
        quarantine_on_graph_invalidity=False,
        prefer_resume_delivery_on_claimable_outbox=True,
        prefer_wait_on_live_lease=False,
        quarantine_on_explicit_reference_drift=False,
    )
    decision = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
        config=config,
    ).resolve(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
    )
    assert decision.action == "quarantine"
    assert decision.reason == "claimable_outbox_while_live_idempotency_lease"
    assert decision.operator_required
    assert decision.delivery_hint == "claimable_outbox"
    assert "claimable_outbox_while_idempotency_lease_live" in (
        decision.anomalies
    )
    assert decision.resume_action == "quarantine"


def test_orchestrator_uses_snapshot_time_for_expired_delivery_claim() -> None:
    now = datetime.now(timezone.utc)
    checkpoints = SequenceCheckpointStore(
        path_to("execution"),
        path_to("execution"),
    )
    expired_idempotency = idempotency_record(IdempotencyState.EXPIRED)
    idempotency = SequenceIdempotencyStore(
        expired_idempotency,
        expired_idempotency,
    )
    delivering = outbox_message(
        OutboxState.DELIVERING,
        available_at=now - timedelta(hours=2),
        claim_expires_at=now - timedelta(hours=1),
    )
    outbox = SequenceOutboxStore(delivering, delivering)

    plan = RecoveryOrchestrator(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    ).plan(
        tenant_id=TENANT,
        run_id=RUN,
        idempotency_key=KEY,
    )

    assert plan.recovery_action == "resume_delivery"
    assert plan.delivery_hint == "expired_delivery_claim_can_be_stolen"
    assert plan.reconciliation.is_clean
    assert checkpoints.calls == [(TENANT, RUN), (TENANT, RUN)]
    assert idempotency.calls == [KEY, KEY]
    assert outbox.calls == [(TENANT, OUTBOX_ID), (TENANT, OUTBOX_ID)]
