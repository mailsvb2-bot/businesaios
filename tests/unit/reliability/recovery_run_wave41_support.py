from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Iterable

from reliability.execution_checkpoint_store import ExecutionCheckpoint
from reliability.idempotency_contract import (
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyState,
)
from reliability.outbox_store import OutboxMessage, OutboxState

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
TENANT = "tenant-a"
RUN = "run-1"
OUTBOX_ID = "message-1"
KEY = IdempotencyKey(
    tenant_id=TENANT,
    namespace="runtime",
    operation="execute",
    key=RUN,
    scope_hash="scope-1",
)


def checkpoint(
    stage: str,
    sequence_no: int,
    *,
    tenant_id: str = TENANT,
    run_id: str = RUN,
    checkpoint_id: str | None = None,
    idempotency_key: str | None = RUN,
    outbox_message_id: str | None = OUTBOX_ID,
    trace_id: str | None = "trace-1",
    decision_id: str | None = "decision-1",
    action_id: str | None = "action-1",
    created_at: datetime = NOW,
) -> ExecutionCheckpoint:
    return ExecutionCheckpoint(
        tenant_id=tenant_id,
        run_id=run_id,
        sequence_no=sequence_no,
        stage=stage,
        checkpoint_id=checkpoint_id or f"cp-{sequence_no}-{stage}",
        created_at=created_at,
        trace_id=trace_id,
        decision_id=decision_id,
        action_id=action_id,
        idempotency_key=idempotency_key,
        outbox_message_id=outbox_message_id,
        payload={},
    )


def path_to(stage: str) -> tuple[ExecutionCheckpoint, ...]:
    stages = (
        "request",
        "world_state",
        "decision",
        "executable_action",
        "execution",
        "verification",
        "state_update",
        "evidence",
        "completed",
    )
    if stage == "failed":
        return (
            checkpoint("request", 0),
            checkpoint("failed", 1),
        )
    index = stages.index(stage)
    return tuple(checkpoint(name, i) for i, name in enumerate(stages[: index + 1]))


def idempotency_record(
    state: IdempotencyState = IdempotencyState.IN_PROGRESS,
    *,
    key: IdempotencyKey = KEY,
    lease_expires_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> IdempotencyRecord:
    if lease_expires_at is None and state is IdempotencyState.IN_PROGRESS:
        lease_expires_at = NOW + timedelta(minutes=5)
    if completed_at is None and state is IdempotencyState.COMPLETED:
        completed_at = NOW
    return IdempotencyRecord(
        idempotency_key=key,
        state=state,
        first_seen_at=NOW,
        updated_at=NOW,
        lease_expires_at=lease_expires_at,
        completed_at=completed_at,
        owner_id="worker-1",
        attempt_count=1,
        result_ref="result-1" if state is IdempotencyState.COMPLETED else None,
        result_digest="digest-1" if state is IdempotencyState.COMPLETED else None,
        failure_reason="failed" if state is IdempotencyState.FAILED else None,
        metadata={},
    )


def outbox_message(
    state: OutboxState = OutboxState.PENDING,
    *,
    tenant_id: str = TENANT,
    message_id: str = OUTBOX_ID,
    run_id: str | None = RUN,
    available_at: datetime = NOW + timedelta(minutes=5),
    claim_expires_at: datetime | None = None,
    delivered_at: datetime | None = None,
    last_error: str | None = None,
) -> OutboxMessage:
    if state is OutboxState.DELIVERED and delivered_at is None:
        delivered_at = NOW
    if state is OutboxState.DEAD and last_error is None:
        last_error = "dead"
    return OutboxMessage(
        tenant_id=tenant_id,
        message_id=message_id,
        topic="effects",
        dedupe_key=f"dedupe-{message_id}",
        payload={"ok": True},
        state=state,
        created_at=NOW,
        updated_at=NOW,
        available_at=available_at,
        claim_owner_id="delivery-1" if state is OutboxState.DELIVERING else None,
        claim_expires_at=claim_expires_at,
        delivery_attempts=1,
        last_error=last_error,
        trace_id="trace-1",
        run_id=run_id,
        decision_id="decision-1",
        delivered_at=delivered_at,
    )


class SequenceCheckpointStore:
    def __init__(self, *responses: Iterable[ExecutionCheckpoint]) -> None:
        self.responses = [tuple(response) for response in responses] or [()]
        self.calls: list[tuple[str, str]] = []

    def list_run(self, *, tenant_id: str, run_id: str):
        self.calls.append((tenant_id, run_id))
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]

    def append(self, checkpoint: ExecutionCheckpoint) -> None:
        raise NotImplementedError

    def latest(self, *, tenant_id: str, run_id: str):
        items = self.list_run(tenant_id=tenant_id, run_id=run_id)
        return items[-1] if items else None


class SequenceIdempotencyStore:
    def __init__(self, *responses: IdempotencyRecord | None) -> None:
        self.responses = list(responses) or [None]
        self.calls: list[IdempotencyKey] = []

    def get(self, *, key: IdempotencyKey):
        self.calls.append(key)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


class SequenceOutboxStore:
    def __init__(self, *responses: OutboxMessage | None) -> None:
        self.responses = list(responses) or [None]
        self.calls: list[tuple[str, str]] = []

    def get(self, *, tenant_id: str, message_id: str):
        self.calls.append((tenant_id, message_id))
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


def with_changes(record, **changes):
    return replace(record, **changes)
